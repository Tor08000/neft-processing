from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.schemas.payouts import (
    PayoutBatchDetail,
    PayoutBatchListResponse,
    PayoutBatchSummary,
    PayoutClosePeriodRequest,
    PayoutExportCreateRequest,
    PayoutExportListResponse,
    PayoutExportOut,
    PayoutExportFormatListResponse,
    PayoutMarkRequest,
    PayoutReconcileResponse,
)
from app.services.payout_exports import (
    PayoutExportConflictError,
    PayoutExportError,
    create_payout_export,
    list_payout_exports,
    load_export,
)
from app.services.payout_export_xlsx import build_filename, list_bank_formats
from app.services.payout_metrics import metrics as payout_metrics
from app.services.payouts_service import (
    PayoutConflictError,
    PayoutError,
    close_payout_period,
    list_payout_batches,
    load_payout_batch,
    mark_batch_sent,
    mark_batch_settled,
    reconcile_batch,
)
from app.services.s3_storage import S3Storage

router = APIRouter(prefix="/api/v1/payouts", tags=["payouts"])


@router.post("/close-period", response_model=PayoutBatchSummary)
def close_period_endpoint(payload: PayoutClosePeriodRequest, db: Session = Depends(get_db)) -> PayoutBatchSummary:
    try:
        batch = close_payout_period(
            db,
            tenant_id=payload.tenant_id,
            partner_id=payload.partner_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
        )
    except ValueError as exc:
        if str(exc) == "invalid_period":
            raise HTTPException(status_code=422, detail="invalid period") from exc
        raise
    items_count = len(batch.items)
    return PayoutBatchSummary(
        batch_id=batch.id,
        state=batch.state.value if hasattr(batch.state, "value") else str(batch.state),
        total_amount=Decimal(batch.total_amount or 0),
        total_qty=Decimal(batch.total_qty or 0),
        operations_count=int(batch.operations_count or 0),
        items_count=items_count,
    )


@router.get("/batches", response_model=PayoutBatchListResponse)
def list_batches_endpoint(
    partner_id: str | None = Query(None),
    state: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PayoutBatchListResponse:
    batches, total = list_payout_batches(
        db,
        partner_id=partner_id,
        state=state,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    items = [PayoutBatchSummary.from_batch(batch) for batch in batches]
    return PayoutBatchListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/batches/{batch_id}", response_model=PayoutBatchDetail)
def get_batch_endpoint(batch_id: str, db: Session = Depends(get_db)) -> PayoutBatchDetail:
    batch = load_payout_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="batch not found")
    return PayoutBatchDetail.from_batch(batch)


@router.post("/batches/{batch_id}/mark-sent", response_model=PayoutBatchSummary)
def mark_sent_endpoint(
    batch_id: str,
    payload: PayoutMarkRequest,
    db: Session = Depends(get_db),
) -> PayoutBatchSummary:
    try:
        batch = mark_batch_sent(
            db,
            batch_id=batch_id,
            provider=payload.provider,
            external_ref=payload.external_ref,
        )
    except PayoutConflictError as exc:
        raise HTTPException(status_code=409, detail="external_ref_conflict") from exc
    except PayoutError as exc:
        detail = "invalid_state" if str(exc) == "invalid_state" else "batch_not_found"
        raise HTTPException(status_code=409 if detail == "invalid_state" else 404, detail=detail) from exc
    return PayoutBatchSummary.from_batch(batch)


@router.post("/batches/{batch_id}/mark-settled", response_model=PayoutBatchSummary)
def mark_settled_endpoint(
    batch_id: str,
    payload: PayoutMarkRequest,
    db: Session = Depends(get_db),
) -> PayoutBatchSummary:
    try:
        batch = mark_batch_settled(
            db,
            batch_id=batch_id,
            provider=payload.provider,
            external_ref=payload.external_ref,
        )
    except PayoutConflictError as exc:
        raise HTTPException(status_code=409, detail="external_ref_conflict") from exc
    except PayoutError as exc:
        detail = "invalid_state" if str(exc) == "invalid_state" else "batch_not_found"
        raise HTTPException(status_code=409 if detail == "invalid_state" else 404, detail=detail) from exc
    return PayoutBatchSummary.from_batch(batch)


@router.get("/batches/{batch_id}/reconcile", response_model=PayoutReconcileResponse)
def reconcile_endpoint(batch_id: str, db: Session = Depends(get_db)) -> PayoutReconcileResponse:
    try:
        result = reconcile_batch(db, batch_id)
    except PayoutError as exc:
        raise HTTPException(status_code=404, detail="batch not found") from exc

    diff_amount = result.computed_amount - result.recorded_amount
    diff_count = result.computed_count - result.recorded_count
    status_value = "OK" if diff_amount == 0 and diff_count == 0 else "MISMATCH"
    return PayoutReconcileResponse(
        batch_id=result.batch.id,
        computed={"total_amount": result.computed_amount, "operations_count": result.computed_count},
        recorded={"total_amount": result.recorded_amount, "operations_count": result.recorded_count},
        diff={"amount": diff_amount, "count": diff_count},
        status=status_value,
    )


@router.post("/batches/{batch_id}/export", response_model=PayoutExportOut)
def create_export_endpoint(
    batch_id: str,
    payload: PayoutExportCreateRequest,
    db: Session = Depends(get_db),
) -> PayoutExportOut:
    try:
        if payload.format.value == "XLSX" and not payload.bank_format_code:
            raise HTTPException(status_code=400, detail="bank_format_required")
        result = create_payout_export(
            db,
            batch_id=batch_id,
            export_format=payload.format,
            provider=payload.provider,
            external_ref=payload.external_ref,
            bank_format_code=payload.bank_format_code,
        )
        export = result.export
        payout_metrics.mark_export(export.format.value, export.state.value)
        if export.size_bytes:
            payout_metrics.mark_export_bytes(export.format.value, int(export.size_bytes))
        return PayoutExportOut.from_export(export)
    except PayoutExportConflictError as exc:
        payout_metrics.mark_export_error()
        raise HTTPException(status_code=409, detail="external_ref_conflict") from exc
    except PayoutExportError as exc:
        payout_metrics.mark_export_error()
        reason = str(exc)
        if reason == "batch_not_found":
            raise HTTPException(status_code=404, detail="batch_not_found") from exc
        if reason == "invalid_state":
            raise HTTPException(status_code=409, detail="invalid_state") from exc
        if reason == "format_not_supported":
            raise HTTPException(status_code=400, detail="format_not_supported") from exc
        if reason == "bank_format_required":
            raise HTTPException(status_code=400, detail="bank_format_required") from exc
        if reason == "bank_format_not_found":
            raise HTTPException(status_code=400, detail="bank_format_not_found") from exc
        raise HTTPException(status_code=400, detail="export_failed") from exc
    except Exception as exc:
        payout_metrics.mark_export_error()
        raise HTTPException(status_code=500, detail="export_failed") from exc


@router.get("/batches/{batch_id}/exports", response_model=PayoutExportListResponse)
def list_exports_endpoint(batch_id: str, db: Session = Depends(get_db)) -> PayoutExportListResponse:
    exports = list_payout_exports(db, batch_id=batch_id)
    items = [PayoutExportOut.from_export(export) for export in exports]
    return PayoutExportListResponse(items=items)


@router.get("/export-formats", response_model=PayoutExportFormatListResponse)
def list_export_formats_endpoint() -> PayoutExportFormatListResponse:
    return PayoutExportFormatListResponse(items=list_bank_formats())


@router.get("/exports/{export_id}/download", dependencies=[Depends(require_admin_user)])
def download_export_endpoint(export_id: str, db: Session = Depends(get_db)) -> Response:
    export = load_export(db, export_id)
    if not export:
        payout_metrics.mark_export_download_error()
        raise HTTPException(status_code=404, detail="export_not_found")
    storage = S3Storage(bucket=export.bucket)
    payload = storage.get_bytes(export.object_key)
    if payload is None:
        payout_metrics.mark_export_download_error()
        raise HTTPException(status_code=404, detail="file_not_found")
    if not export.batch:
        payout_metrics.mark_export_download_error()
        raise HTTPException(status_code=404, detail="batch_not_found")
    content_type = "text/csv"
    extension = "csv"
    if export.format.value == "XLSX":
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extension = "xlsx"
    if export.format.value == "XLSX":
        try:
            filename = build_filename(
                format_code=export.bank_format_code,
                partner_id=export.batch.partner_id,
                date_from=export.batch.date_from,
                date_to=export.batch.date_to,
                external_ref=export.external_ref,
            )
        except ValueError:
            filename = (
                f"payout_{export.batch.partner_id}_{export.batch.date_from.isoformat()}_"
                f"{export.batch.date_to.isoformat()}.{extension}"
            )
    else:
        filename = (
            f"payout_{export.batch.partner_id}_{export.batch.date_from.isoformat()}_"
            f"{export.batch.date_to.isoformat()}.{extension}"
        )
    payout_metrics.mark_export_download(export.format.value)
    return Response(
        content=payload,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["router"]
