from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.accounting_export_batch import AccountingExportFormat, AccountingExportState, AccountingExportType
from app.schemas.admin.accounting_exports import (
    AccountingExportBatchListResponse,
    AccountingExportBatchRead,
    AccountingExportCreateRequest,
)
from app.services.accounting_export_service import (
    AccountingExportError,
    AccountingExportForbidden,
    AccountingExportInvalidState,
    AccountingExportNotFound,
    AccountingExportService,
)
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.policy import PolicyAccessDenied

router = APIRouter(prefix="/accounting", tags=["admin-accounting"])


@router.post("/exports", response_model=AccountingExportBatchRead, status_code=status.HTTP_201_CREATED)
def create_export(
    body: AccountingExportCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> AccountingExportBatchRead:
    service = AccountingExportService(db)
    try:
        batch = service.create_export(
            period_id=body.period_id,
            export_type=body.export_type,
            export_format=body.format,
            version=body.version,
            force=body.force,
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
            token=token,
        )
        db.commit()
    except PolicyAccessDenied as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AccountingExportForbidden as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AccountingExportNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccountingExportError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AccountingExportBatchRead.model_validate(batch)


@router.post("/exports/{batch_id}/generate", response_model=AccountingExportBatchRead)
def generate_export(
    batch_id: str,
    request: Request,
    force: bool = Query(False),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> AccountingExportBatchRead:
    service = AccountingExportService(db)
    try:
        batch = service.generate_export(
            batch_id=batch_id,
            force=force,
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
            token=token,
        )
        db.commit()
    except PolicyAccessDenied as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AccountingExportForbidden as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AccountingExportInvalidState as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AccountingExportNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccountingExportError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AccountingExportBatchRead.model_validate(batch)


@router.get("/exports/{batch_id}", response_model=AccountingExportBatchRead)
def get_export(
    batch_id: str,
    db: Session = Depends(get_db),
) -> AccountingExportBatchRead:
    service = AccountingExportService(db)
    try:
        batch = service._load_batch(batch_id)
    except AccountingExportNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AccountingExportBatchRead.model_validate(batch)


@router.get("/exports", response_model=AccountingExportBatchListResponse)
def list_exports(
    period_id: str | None = Query(None),
    state: AccountingExportState | None = Query(None),
    export_type: AccountingExportType | None = Query(None),
    export_format: AccountingExportFormat | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AccountingExportBatchListResponse:
    service = AccountingExportService(db)
    items, total = service.list_exports(
        period_id=period_id,
        state=state,
        export_type=export_type,
        export_format=export_format,
        limit=limit,
        offset=offset,
    )
    return AccountingExportBatchListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/exports/{batch_id}/download")
def download_export(
    batch_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> Response:
    service = AccountingExportService(db)
    try:
        payload = service.download_export(
            batch_id=batch_id,
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )
        batch = service._load_batch(batch_id)
        db.commit()
    except AccountingExportNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccountingExportInvalidState as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AccountingExportError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    extension = "csv" if batch.format == AccountingExportFormat.CSV else "json"
    filename = f"accounting_{batch.billing_period_id}_{batch.export_type.value.lower()}.{extension}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type=service._content_type(batch.format), headers=headers)


@router.post("/exports/{batch_id}/confirm", response_model=AccountingExportBatchRead)
def confirm_export(
    batch_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> AccountingExportBatchRead:
    service = AccountingExportService(db)
    try:
        batch = service.confirm_export(
            batch_id=batch_id,
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
            token=token,
        )
        db.commit()
    except PolicyAccessDenied as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AccountingExportNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccountingExportError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AccountingExportBatchRead.model_validate(batch)


__all__ = ["router"]
