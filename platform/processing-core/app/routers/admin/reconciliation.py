from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.config import settings
from app.db import get_db
from app.db.types import new_uuid_str
from app.models.audit_log import AuditLog, AuditVisibility
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.reconciliation import (
    ExternalStatement,
    ReconciliationDiscrepancy,
    ReconciliationDiscrepancyStatus,
    ReconciliationDiscrepancyType,
    ReconciliationLink,
    ReconciliationLinkStatus,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
)
from app.schemas.admin.reconciliation import (
    ExternalStatementExplain,
    ExternalStatementListResponse,
    ExternalStatementResponse,
    ExternalStatementUploadRequest,
    IgnoreDiscrepancyRequest,
    ReconciliationAdjustmentExplain,
    ReconciliationAdjustmentPosting,
    ReconciliationAuditEvent,
    ReconciliationDiscrepancyListResponse,
    ReconciliationDiscrepancyResponse,
    ReconciliationDiscrepancyResult,
    ReconciliationExternalRunRequest,
    ReconciliationLinkCounts,
    ReconciliationLinkListResponse,
    ReconciliationLinkResponse,
    ReconciliationRunCreateRequest,
    ReconciliationRunExportResponse,
    ReconciliationRunListResponse,
    ReconciliationRunResponse,
    ReconciliationStatementSummary,
    ReconciliationStatementTotalCheck,
    ResolveDiscrepancyRequest,
)
from app.schemas.admin.reconciliation_fixtures import (
    ReconciliationFixtureBundleResponse,
    ReconciliationFixtureCreateRequest,
    ReconciliationFixtureFile,
    ReconciliationFixtureImportCreateRequest,
    ReconciliationFixtureImportCreateResponse,
)
from app.services.bank_stub_service import (
    BankStubServiceError,
    build_external_hash,
    build_external_statement_payload,
    generate_statement,
)
from app.services.bank_statement_reconciliation import create_import_record
from app.services.reconciliation_fixtures import FixtureStorage, generate_fixture_bundle
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.reconciliation_service import (
    ignore_discrepancy,
    resolve_discrepancy_with_adjustment,
    run_external_reconciliation,
    run_internal_reconciliation,
    upload_external_statement,
)
from app.security.rbac.guard import require_permission

router = APIRouter(
    prefix="/reconciliation",
    tags=["admin", "reconciliation"],
    dependencies=[Depends(require_permission("admin:reconciliation:*"))],
)


@router.post("/internal", response_model=ReconciliationRunResponse, status_code=201)
def create_internal_run(
    payload: ReconciliationRunCreateRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ReconciliationRunResponse:
    if payload.period_start > payload.period_end:
        raise HTTPException(status_code=422, detail="invalid_period")
    run_id = run_internal_reconciliation(
        db,
        period_start=payload.period_start,
        period_end=payload.period_end,
        created_by=token.get("user_id") or token.get("sub"),
    )
    db.commit()
    run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).one()
    return _serialize_run(run)


@router.post("/external/run", response_model=ReconciliationRunResponse, status_code=201)
def create_external_run(
    payload: ReconciliationExternalRunRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ReconciliationRunResponse:
    run_id = run_external_reconciliation(
        db,
        statement_id=payload.statement_id,
        created_by=token.get("user_id") or token.get("sub"),
    )
    db.commit()
    run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).one()
    return _serialize_run(run)


@router.post("/run", response_model=ReconciliationRunResponse, status_code=201)
def run_stubbed_external(
    request: Request,
    source: str = Query(...),
    period_from: datetime = Query(...),
    period_to: datetime = Query(...),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ReconciliationRunResponse:
    if source != "bank_stub":
        raise HTTPException(status_code=422, detail="invalid_source")
    if not settings.BANK_STUB_ENABLED:
        raise HTTPException(status_code=404, detail="bank_stub_disabled")
    if period_from > period_to:
        raise HTTPException(status_code=422, detail="invalid_period")

    created_by = token.get("user_id") or token.get("sub")
    actor = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    try:
        statement = generate_statement(
            db,
            tenant_id=int(token.get("tenant_id") or 0),
            period_from=period_from,
            period_to=period_to,
            actor=actor,
        )
    except BankStubServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = build_external_statement_payload(statement)
    currency = payload.get("currency") or "RUB"
    total_in_raw = payload.get("total_in")
    total_out_raw = payload.get("total_out")
    closing_raw = payload.get("closing_balance")
    total_in = Decimal(str(total_in_raw)) if total_in_raw is not None else None
    total_out = Decimal(str(total_out_raw)) if total_out_raw is not None else None
    closing_balance = Decimal(str(closing_raw)) if closing_raw is not None else None
    try:
        external = upload_external_statement(
            db,
            provider="bank_stub",
            period_start=statement.period_from,
            period_end=statement.period_to,
            currency=currency,
            total_in=total_in,
            total_out=total_out,
            closing_balance=closing_balance,
            lines=payload.get("lines"),
            created_by=created_by,
        )
    except ValueError as exc:
        if str(exc) != "statement_already_uploaded":
            raise
        source_hash = build_external_hash(statement)
        external = (
            db.query(ExternalStatement)
            .filter(ExternalStatement.provider == "bank_stub")
            .filter(ExternalStatement.source_hash == source_hash)
            .one()
        )

    run_id = run_external_reconciliation(
        db,
        statement_id=str(external.id),
        created_by=created_by,
    )
    db.commit()
    run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).one()
    return _serialize_run(run)


@router.post("/fixtures", response_model=ReconciliationFixtureBundleResponse, status_code=201)
def create_fixture_bundle(
    payload: ReconciliationFixtureCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ReconciliationFixtureBundleResponse:
    try:
        files, meta = generate_fixture_bundle(
            db=db,
            scenario=payload.scenario,
            invoice_id=payload.invoice_id,
            org_id=payload.org_id,
            currency=payload.currency,
            wrong_amount_mode=payload.wrong_amount_mode,
            amount_delta=payload.amount_delta,
            payer_inn=payload.payer_inn,
            payer_name=payload.payer_name,
            seed=payload.seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    bundle_id = new_uuid_str()
    storage = FixtureStorage()
    formats = [payload.format] if payload.format != "ALL" else list(files.keys())
    response_files: list[ReconciliationFixtureFile] = []

    for fmt in formats:
        payload_bytes = files.get(fmt)
        if payload_bytes is None:
            continue
        suffix = "csv" if fmt == "CSV" else "txt" if fmt == "CLIENT_BANK_1C" else "mt940"
        file_name = f"{payload.scenario.lower()}.{suffix}"
        object_key = storage.build_object_key(bundle_id=bundle_id, file_name=file_name)
        content_type = "text/csv" if fmt == "CSV" else "text/plain"
        try:
            storage.put_bytes(object_key=object_key, payload=payload_bytes, content_type=content_type)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail="fixture_storage_unavailable") from exc
        download_url = storage.presign_download(
            object_key=object_key,
            expires=settings.S3_SIGNED_URL_TTL_SECONDS,
        )
        if not download_url:
            raise HTTPException(status_code=500, detail="fixture_presign_failed")
        response_files.append(
            ReconciliationFixtureFile(format=fmt, file_name=file_name, download_url=download_url)
        )

    AuditService(db).audit(
        event_type="recon_fixture_generated",
        entity_type="reconciliation_fixture_bundle",
        entity_id=bundle_id,
        action="GENERATE",
        visibility=AuditVisibility.INTERNAL,
        after={
            "scenario": payload.scenario,
            "invoice_id": payload.invoice_id,
            "formats": formats,
            "amount": str(meta.get("amount")),
            "currency": meta.get("currency"),
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    db.commit()

    return ReconciliationFixtureBundleResponse(
        bundle_id=bundle_id,
        files=response_files,
        notes="Upload any of these into reconciliation imports.",
    )


@router.post("/fixtures/{bundle_id}/create-import", response_model=ReconciliationFixtureImportCreateResponse)
def create_fixture_import(
    bundle_id: str,
    payload: ReconciliationFixtureImportCreateRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ReconciliationFixtureImportCreateResponse:
    storage = FixtureStorage()
    object_key = storage.build_object_key(bundle_id=bundle_id, file_name=payload.file_name)
    if not storage.exists(object_key=object_key):
        raise HTTPException(status_code=404, detail="fixture_file_not_found")

    import_id = new_uuid_str()
    record = create_import_record(
        db,
        import_id=import_id,
        admin_id=token.get("user_id") or token.get("sub"),
        file_object_key=object_key,
        fmt=payload.format,
        period_from=None,
        period_to=None,
    )
    db.commit()
    return ReconciliationFixtureImportCreateResponse(import_id=str(record["id"]), object_key=object_key)


@router.get("/runs", response_model=ReconciliationRunListResponse)
def list_runs(
    scope: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReconciliationRunListResponse:
    query = db.query(ReconciliationRun)
    if scope:
        query = query.filter(ReconciliationRun.scope == scope)
    if provider:
        query = query.filter(ReconciliationRun.provider == provider)
    if status:
        query = query.filter(ReconciliationRun.status == status)
    runs = query.order_by(ReconciliationRun.created_at.desc()).all()
    return ReconciliationRunListResponse(runs=[_serialize_run(run) for run in runs])


@router.get("/runs/{run_id}", response_model=ReconciliationRunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)) -> ReconciliationRunResponse:
    run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="reconciliation_run_not_found")
    statement = _statement_for_run(db, run=run)
    return _serialize_run(
        run,
        statement=statement,
        timeline=_audit_events_for_entity(db, entity_type="reconciliation_run", entity_id=str(run.id)),
        link_counts=_link_counts_for_run(db, run),
    )


@router.get("/runs/{run_id}/discrepancies", response_model=ReconciliationDiscrepancyListResponse)
def list_discrepancies(run_id: str, db: Session = Depends(get_db)) -> ReconciliationDiscrepancyListResponse:
    discrepancies = (
        db.query(ReconciliationDiscrepancy)
        .filter(ReconciliationDiscrepancy.run_id == run_id)
        .order_by(ReconciliationDiscrepancy.created_at.asc())
        .all()
    )
    timeline_by_discrepancy = _audit_events_for_entities(
        db,
        entity_type="reconciliation_discrepancy",
        entity_ids=[str(item.id) for item in discrepancies],
    )
    adjustment_explain_by_discrepancy = _adjustment_explain_by_discrepancy(db, discrepancies=discrepancies)
    return ReconciliationDiscrepancyListResponse(
        discrepancies=[
            _serialize_discrepancy(
                item,
                timeline=timeline_by_discrepancy.get(str(item.id), []),
                adjustment_explain=adjustment_explain_by_discrepancy.get(str(item.id)),
            )
            for item in discrepancies
        ]
    )


@router.get("/runs/{run_id}/links", response_model=ReconciliationLinkListResponse)
def list_run_links(
    run_id: str,
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReconciliationLinkListResponse:
    run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="reconciliation_run_not_found")
    query = db.query(ReconciliationLink).filter(ReconciliationLink.run_id == run_id)
    if status:
        query = query.filter(ReconciliationLink.status == status)
    links = query.order_by(ReconciliationLink.expected_at.asc(), ReconciliationLink.created_at.asc()).all()
    discrepancies_by_entity = _discrepancies_by_entity(db, run_id=run_id)
    return ReconciliationLinkListResponse(
        links=[_serialize_link(item, discrepancies_by_entity=discrepancies_by_entity) for item in links]
    )


@router.get("/runs/{run_id}/export", response_model=ReconciliationRunExportResponse)
def export_run(
    run_id: str,
    format: Literal["payload", "json", "csv"] = Query(default="payload"),
    export_scope: Literal["full", "discrepancies"] = Query(default="full"),
    discrepancy_status: str | None = Query(default=None),
    discrepancy_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReconciliationRunExportResponse | Response:
    run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="reconciliation_run_not_found")
    payload = _build_run_export_payload(
        db,
        run=run,
        export_scope=export_scope,
        discrepancy_status=discrepancy_status,
        discrepancy_type=discrepancy_type,
    )
    if format == "json":
        return JSONResponse(
            content=jsonable_encoder(payload.model_dump(mode="json")),
            headers={"Content-Disposition": f'attachment; filename="reconciliation_run_{run_id}.json"'},
        )
    if format == "csv":
        return PlainTextResponse(
            content=_build_run_export_csv(
                payload,
                include_summary_row=export_scope == "full" and discrepancy_status is None and discrepancy_type is None,
            ),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="reconciliation_run_{run_id}.csv"'},
        )
    return payload


@router.get("/discrepancies/{discrepancy_id}", response_model=ReconciliationDiscrepancyResult)
def get_discrepancy(discrepancy_id: str, db: Session = Depends(get_db)) -> ReconciliationDiscrepancyResult:
    discrepancy = (
        db.query(ReconciliationDiscrepancy)
        .filter(ReconciliationDiscrepancy.id == discrepancy_id)
        .one_or_none()
    )
    if discrepancy is None:
        raise HTTPException(status_code=404, detail="reconciliation_discrepancy_not_found")
    adjustment_explain = _adjustment_explain_by_discrepancy(db, discrepancies=[discrepancy]).get(str(discrepancy.id))
    return ReconciliationDiscrepancyResult(
        discrepancy=_serialize_discrepancy(
            discrepancy,
            timeline=_build_discrepancy_timeline(db, discrepancy=discrepancy, adjustment_explain=adjustment_explain),
            adjustment_explain=adjustment_explain,
        )
    )


def _build_run_export_payload(
    db: Session,
    *,
    run: ReconciliationRun,
    export_scope: Literal["full", "discrepancies"] = "full",
    discrepancy_status: str | None = None,
    discrepancy_type: str | None = None,
) -> ReconciliationRunExportResponse:
    run_id = str(run.id)
    statement = _statement_for_run(db, run=run)
    discrepancies = _discrepancies_for_run(
        db,
        run_id=run_id,
        discrepancy_status=discrepancy_status,
        discrepancy_type=discrepancy_type,
    )
    filtered_discrepancy_ids = {str(item.id) for item in discrepancies}
    links = (
        db.query(ReconciliationLink)
        .filter(ReconciliationLink.run_id == run_id)
        .order_by(ReconciliationLink.expected_at.asc(), ReconciliationLink.created_at.asc())
        .all()
    )
    discrepancies_by_entity = _discrepancies_by_entity(db, run_id=run_id)
    adjustment_explain_by_discrepancy = _adjustment_explain_by_discrepancy(db, discrepancies=discrepancies)
    serialized_links = [_serialize_link(item, discrepancies_by_entity=discrepancies_by_entity) for item in links]
    if export_scope == "discrepancies" or discrepancy_status is not None or discrepancy_type is not None:
        serialized_links = [
            item for item in serialized_links if filtered_discrepancy_ids.intersection(set(item.discrepancy_ids))
        ]
    return ReconciliationRunExportResponse(
        exported_at=datetime.now(timezone.utc),
        run=_serialize_run(
            run,
            statement=statement,
            timeline=_audit_events_for_entity(db, entity_type="reconciliation_run", entity_id=str(run.id)),
            link_counts=_link_counts_for_run(db, run),
        ),
        discrepancies=[
            _serialize_discrepancy(
                item,
                timeline=_build_discrepancy_timeline(
                    db,
                    discrepancy=item,
                    adjustment_explain=adjustment_explain_by_discrepancy.get(str(item.id)),
                ),
                adjustment_explain=adjustment_explain_by_discrepancy.get(str(item.id)),
            )
            for item in discrepancies
        ],
        links=serialized_links,
    )


def _build_run_export_csv(payload: ReconciliationRunExportResponse, *, include_summary_row: bool) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "run_id",
            "scope",
            "provider",
            "period_start",
            "period_end",
            "status",
            "statement_id",
            "discrepancy_id",
            "discrepancy_type",
            "discrepancy_status",
            "currency",
            "internal_amount",
            "external_amount",
            "delta",
            "adjustment_tx_id",
            "entity_type",
            "entity_id",
            "link_status",
            "review_status",
            "match_key",
        ],
    )
    writer.writeheader()
    links_by_discrepancy_id: dict[str, ReconciliationLinkResponse] = {}
    for link in payload.links:
        for discrepancy_id in link.discrepancy_ids:
            links_by_discrepancy_id.setdefault(discrepancy_id, link)

    rows_written = 0
    for discrepancy in payload.discrepancies:
        linked = links_by_discrepancy_id.get(discrepancy.id)
        writer.writerow(
            {
                "run_id": payload.run.id,
                "scope": payload.run.scope.value if hasattr(payload.run.scope, "value") else payload.run.scope,
                "provider": payload.run.provider or "",
                "period_start": payload.run.period_start.isoformat(),
                "period_end": payload.run.period_end.isoformat(),
                "status": payload.run.status.value if hasattr(payload.run.status, "value") else payload.run.status,
                "statement_id": payload.run.statement.id if payload.run.statement else "",
                "discrepancy_id": discrepancy.id,
                "discrepancy_type": discrepancy.discrepancy_type.value
                if hasattr(discrepancy.discrepancy_type, "value")
                else discrepancy.discrepancy_type,
                "discrepancy_status": discrepancy.status.value if hasattr(discrepancy.status, "value") else discrepancy.status,
                "currency": discrepancy.currency,
                "internal_amount": discrepancy.internal_amount if discrepancy.internal_amount is not None else "",
                "external_amount": discrepancy.external_amount if discrepancy.external_amount is not None else "",
                "delta": discrepancy.delta if discrepancy.delta is not None else "",
                "adjustment_tx_id": discrepancy.adjustment_explain.adjustment_tx_id if discrepancy.adjustment_explain else "",
                "entity_type": linked.entity_type if linked else "",
                "entity_id": linked.entity_id if linked else "",
                "link_status": linked.status if linked else "",
                "review_status": linked.review_status.value if linked and linked.review_status else "",
                "match_key": linked.match_key if linked and linked.match_key else "",
            }
        )
        rows_written += 1

    if rows_written == 0 and include_summary_row:
        writer.writerow(
            {
                "run_id": payload.run.id,
                "scope": payload.run.scope.value if hasattr(payload.run.scope, "value") else payload.run.scope,
                "provider": payload.run.provider or "",
                "period_start": payload.run.period_start.isoformat(),
                "period_end": payload.run.period_end.isoformat(),
                "status": payload.run.status.value if hasattr(payload.run.status, "value") else payload.run.status,
                "statement_id": payload.run.statement.id if payload.run.statement else "",
            }
        )

    return buffer.getvalue()


@router.post("/external/statements", response_model=ExternalStatementResponse, status_code=201)
def upload_statement(
    payload: ExternalStatementUploadRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ExternalStatementResponse:
    if payload.period_start > payload.period_end:
        raise HTTPException(status_code=422, detail="invalid_period")
    try:
        statement = upload_external_statement(
            db,
            provider=payload.provider,
            period_start=payload.period_start,
            period_end=payload.period_end,
            currency=payload.currency,
            total_in=payload.total_in,
            total_out=payload.total_out,
            closing_balance=payload.closing_balance,
            lines=payload.lines,
            created_by=token.get("user_id") or token.get("sub"),
        )
    except ValueError as exc:
        if str(exc) == "statement_already_uploaded":
            raise HTTPException(status_code=409, detail="statement_already_uploaded") from exc
        raise
    db.commit()
    return _serialize_statement(statement)


@router.get("/external/statements/{statement_id}", response_model=ExternalStatementResponse)
def get_statement(statement_id: str, db: Session = Depends(get_db)) -> ExternalStatementResponse:
    statement = db.query(ExternalStatement).filter(ExternalStatement.id == statement_id).one_or_none()
    if statement is None:
        raise HTTPException(status_code=404, detail="external_statement_not_found")
    return _serialize_statement(
        statement,
        explain=_build_statement_explain(db, statement=statement),
        timeline=_audit_events_for_entity(db, entity_type="external_statement", entity_id=str(statement.id)),
    )


@router.get("/external/statements/{statement_id}/discrepancies", response_model=ReconciliationDiscrepancyListResponse)
def list_statement_discrepancies(
    statement_id: str,
    status: str | None = Query(default=None),
    discrepancy_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReconciliationDiscrepancyListResponse:
    statement = db.query(ExternalStatement).filter(ExternalStatement.id == statement_id).one_or_none()
    if statement is None:
        raise HTTPException(status_code=404, detail="external_statement_not_found")
    discrepancies = _discrepancies_for_statement(
        db,
        statement=statement,
        discrepancy_status=status,
        discrepancy_type=discrepancy_type,
    )
    adjustment_explain_by_discrepancy = _adjustment_explain_by_discrepancy(db, discrepancies=discrepancies)
    return ReconciliationDiscrepancyListResponse(
        discrepancies=[
            _serialize_discrepancy(
                item,
                timeline=_build_discrepancy_timeline(
                    db,
                    discrepancy=item,
                    adjustment_explain=adjustment_explain_by_discrepancy.get(str(item.id)),
                ),
                adjustment_explain=adjustment_explain_by_discrepancy.get(str(item.id)),
            )
            for item in discrepancies
        ]
    )


@router.get("/external/statements", response_model=ExternalStatementListResponse)
def list_statements(
    provider: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ExternalStatementListResponse:
    query = db.query(ExternalStatement)
    if provider:
        query = query.filter(ExternalStatement.provider == provider)
    statements = query.order_by(ExternalStatement.period_end.desc()).all()
    return ExternalStatementListResponse(statements=[_serialize_statement(item) for item in statements])


@router.post("/discrepancies/{discrepancy_id}/resolve-adjustment", response_model=dict)
def resolve_discrepancy(
    discrepancy_id: str,
    payload: ResolveDiscrepancyRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    try:
        tx_id = resolve_discrepancy_with_adjustment(
            db,
            discrepancy_id,
            note=payload.note,
            created_by=token.get("user_id") or token.get("sub"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"adjustment_tx_id": tx_id}


@router.post("/discrepancies/{discrepancy_id}/ignore", response_model=dict)
def ignore_discrepancy_endpoint(
    discrepancy_id: str,
    payload: IgnoreDiscrepancyRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    try:
        ignore_discrepancy(
            db,
            discrepancy_id,
            reason=payload.reason,
            created_by=token.get("user_id") or token.get("sub"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"status": "ignored"}


def _serialize_audit_event(item: AuditLog) -> ReconciliationAuditEvent:
    return ReconciliationAuditEvent(
        ts=_coerce_utc(item.ts),
        event_type=item.event_type,
        entity_type=item.entity_type,
        entity_id=item.entity_id,
        action=item.action,
        reason=item.reason,
        actor_id=item.actor_id,
        actor_email=item.actor_email,
        before=item.before if isinstance(item.before, dict) else None,
        after=item.after if isinstance(item.after, dict) else None,
    )


def _audit_events_for_entity(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    limit: int = 20,
) -> list[ReconciliationAuditEvent]:
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.ts.desc(), AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_audit_event(item) for item in rows]


def _audit_events_for_entities(
    db: Session,
    *,
    entity_type: str,
    entity_ids: list[str],
    limit: int = 20,
) -> dict[str, list[ReconciliationAuditEvent]]:
    if not entity_ids:
        return {}
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == entity_type, AuditLog.entity_id.in_(entity_ids))
        .order_by(AuditLog.entity_id.asc(), AuditLog.ts.desc(), AuditLog.id.desc())
        .all()
    )
    result: dict[str, list[ReconciliationAuditEvent]] = {}
    for item in rows:
        bucket = result.setdefault(str(item.entity_id), [])
        if len(bucket) >= limit:
            continue
        bucket.append(_serialize_audit_event(item))
    return result


def _serialize_statement_summary(item: ExternalStatement) -> ReconciliationStatementSummary:
    return ReconciliationStatementSummary(
        id=str(item.id),
        provider=item.provider,
        period_start=item.period_start,
        period_end=item.period_end,
        currency=item.currency,
        total_in=item.total_in,
        total_out=item.total_out,
        closing_balance=item.closing_balance,
        created_at=item.created_at,
        source_hash=item.source_hash,
        audit_event_id=str(item.audit_event_id) if item.audit_event_id else None,
    )


def _adjustment_explain_by_discrepancy(
    db: Session,
    *,
    discrepancies: list[ReconciliationDiscrepancy],
) -> dict[str, ReconciliationAdjustmentExplain]:
    discrepancy_to_tx: dict[str, str] = {}
    for item in discrepancies:
        resolution = item.resolution if isinstance(item.resolution, dict) else {}
        tx_id = resolution.get("adjustment_tx_id")
        if tx_id:
            discrepancy_to_tx[str(item.id)] = str(tx_id)
    if not discrepancy_to_tx:
        return {}

    transactions = (
        db.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.id.in_(list(discrepancy_to_tx.values())))
        .all()
    )
    tx_map = {str(item.id): item for item in transactions}
    postings_by_tx: dict[str, list[ReconciliationAdjustmentPosting]] = {}
    audit_events_by_tx = _audit_events_for_entities(
        db,
        entity_type="internal_ledger_transaction",
        entity_ids=list(discrepancy_to_tx.values()),
    )
    posting_rows = (
        db.query(InternalLedgerEntry, InternalLedgerAccount)
        .join(InternalLedgerAccount, InternalLedgerEntry.account_id == InternalLedgerAccount.id)
        .filter(InternalLedgerEntry.ledger_transaction_id.in_(list(discrepancy_to_tx.values())))
        .order_by(InternalLedgerEntry.created_at.asc(), InternalLedgerEntry.id.asc())
        .all()
    )
    for entry, account in posting_rows:
        postings_by_tx.setdefault(str(entry.ledger_transaction_id), []).append(
            ReconciliationAdjustmentPosting(
                account_id=str(account.id),
                account_type=account.account_type,
                client_id=account.client_id,
                direction=entry.direction,
                amount=int(entry.amount),
                currency=entry.currency,
                entry_hash=entry.entry_hash,
            )
        )

    result: dict[str, ReconciliationAdjustmentExplain] = {}
    for discrepancy_id, tx_id in discrepancy_to_tx.items():
        tx = tx_map.get(tx_id)
        if tx is None:
            continue
        result[discrepancy_id] = ReconciliationAdjustmentExplain(
            adjustment_tx_id=str(tx.id),
            transaction_type=tx.transaction_type,
            external_ref_type=tx.external_ref_type,
            external_ref_id=str(tx.external_ref_id) if tx.external_ref_id else None,
            tenant_id=tx.tenant_id,
            currency=tx.currency,
            total_amount=int(tx.total_amount) if tx.total_amount is not None else None,
            posted_at=tx.posted_at,
            meta=tx.meta if isinstance(tx.meta, dict) else None,
            entries=postings_by_tx.get(tx_id, []),
            audit_events=audit_events_by_tx.get(tx_id, []),
        )
    return result


def _build_discrepancy_timeline(
    db: Session,
    *,
    discrepancy: ReconciliationDiscrepancy,
    adjustment_explain: ReconciliationAdjustmentExplain | None,
) -> list[ReconciliationAuditEvent]:
    synthetic_created = ReconciliationAuditEvent(
        ts=_coerce_utc(discrepancy.created_at),
        event_type="DISCREPANCY_DETECTED",
        entity_type="reconciliation_discrepancy",
        entity_id=str(discrepancy.id),
        action="created",
        after={
            "discrepancy_id": str(discrepancy.id),
            "run_id": str(discrepancy.run_id),
            "discrepancy_type": discrepancy.discrepancy_type.value,
            "status": discrepancy.status.value,
            "details": discrepancy.details if isinstance(discrepancy.details, dict) else None,
            "resolution": discrepancy.resolution if isinstance(discrepancy.resolution, dict) else None,
        },
    )
    timeline = [synthetic_created]
    timeline.extend(
        _audit_events_for_entity(
            db,
            entity_type="reconciliation_discrepancy",
            entity_id=str(discrepancy.id),
        )
    )
    if adjustment_explain is not None:
        timeline.extend(adjustment_explain.audit_events)

    deduped: dict[tuple[str, str, str, str, str], ReconciliationAuditEvent] = {}
    for event in timeline:
        key = (
            event.ts.isoformat(),
            event.event_type,
            event.entity_type,
            event.entity_id,
            event.action,
        )
        deduped.setdefault(key, event)
    return sorted(
        deduped.values(),
        key=lambda item: (_coerce_utc(item.ts), item.event_type, item.entity_type, item.entity_id),
        reverse=True,
    )


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _summary_link_counts(summary: dict[str, object] | None) -> ReconciliationLinkCounts | None:
    if not isinstance(summary, dict):
        return None
    nested = summary.get("links")
    if isinstance(nested, dict):
        return ReconciliationLinkCounts(
            matched=int(nested.get("matched") or 0),
            mismatched=int(nested.get("mismatched") or 0),
            pending=int(nested.get("pending") or 0),
        )
    if any(key in summary for key in ("links_matched", "links_mismatched", "links_pending")):
        return ReconciliationLinkCounts(
            matched=int(summary.get("links_matched") or 0),
            mismatched=int(summary.get("links_mismatched") or 0),
            pending=int(summary.get("links_pending") or 0),
        )
    return None


def _link_counts_for_run(db: Session, run: ReconciliationRun) -> ReconciliationLinkCounts | None:
    rows = db.query(ReconciliationLink).filter(ReconciliationLink.run_id == run.id).all()
    if not rows:
        return _summary_link_counts(run.summary if isinstance(run.summary, dict) else None)
    counts = ReconciliationLinkCounts()
    for item in rows:
        if item.status == ReconciliationLinkStatus.MATCHED:
            counts.matched += 1
        elif item.status == ReconciliationLinkStatus.MISMATCHED:
            counts.mismatched += 1
    summary_counts = _summary_link_counts(run.summary if isinstance(run.summary, dict) else None)
    if summary_counts is not None:
        counts.pending = summary_counts.pending
    return counts


def _statement_for_run(db: Session, *, run: ReconciliationRun) -> ReconciliationStatementSummary | None:
    if run.scope != ReconciliationScope.EXTERNAL:
        return None
    summary = run.summary if isinstance(run.summary, dict) else {}
    statement_id = summary.get("statement_id")
    if statement_id:
        statement = db.query(ExternalStatement).filter(ExternalStatement.id == str(statement_id)).one_or_none()
        if statement is not None:
            return _serialize_statement_summary(statement)
    candidates = (
        db.query(ExternalStatement)
        .filter(
            ExternalStatement.provider == run.provider,
            ExternalStatement.period_start == run.period_start,
            ExternalStatement.period_end == run.period_end,
        )
        .order_by(ExternalStatement.created_at.desc())
        .all()
    )
    if not candidates:
        return None
    return _serialize_statement_summary(candidates[0])


def _related_run_for_statement(
    db: Session,
    *,
    statement: ExternalStatement,
) -> tuple[ReconciliationRun | None, str | None]:
    runs = (
        db.query(ReconciliationRun)
        .filter(
            ReconciliationRun.scope == ReconciliationScope.EXTERNAL,
            ReconciliationRun.provider == statement.provider,
            ReconciliationRun.period_start == statement.period_start,
            ReconciliationRun.period_end == statement.period_end,
        )
        .order_by(ReconciliationRun.created_at.desc())
        .all()
    )
    statement_id = str(statement.id)
    for run in runs:
        summary = run.summary if isinstance(run.summary, dict) else {}
        if str(summary.get("statement_id") or "") == statement_id:
            return run, "summary"
    if len(runs) == 1:
        return runs[0], "provider_period_unique"
    if runs:
        return runs[0], "provider_period_latest"
    return None, None


def _statement_total_checks(
    *,
    statement: ExternalStatement,
    run: ReconciliationRun | None,
    discrepancies: list[ReconciliationDiscrepancy],
) -> list[ReconciliationStatementTotalCheck]:
    discrepancy_by_kind: dict[str, ReconciliationDiscrepancy] = {}
    for item in discrepancies:
        details = item.details if isinstance(item.details, dict) else {}
        kind = details.get("kind")
        if isinstance(kind, str):
            discrepancy_by_kind[kind] = item
    internal_totals = {}
    if run and isinstance(run.summary, dict) and isinstance(run.summary.get("internal_totals"), dict):
        internal_totals = run.summary.get("internal_totals") or {}

    checks: list[ReconciliationStatementTotalCheck] = []
    for kind, external_amount in (
        ("total_in", statement.total_in),
        ("total_out", statement.total_out),
        ("closing_balance", statement.closing_balance),
    ):
        discrepancy = discrepancy_by_kind.get(kind)
        if external_amount is None:
            checks.append(ReconciliationStatementTotalCheck(kind=kind, status="not_provided"))
            continue
        if discrepancy is not None:
            checks.append(
                ReconciliationStatementTotalCheck(
                    kind=kind,
                    status=(
                        "mismatch"
                        if discrepancy.status == ReconciliationDiscrepancyStatus.OPEN
                        else discrepancy.status.value
                    ),
                    external_amount=discrepancy.external_amount,
                    internal_amount=discrepancy.internal_amount,
                    delta=discrepancy.delta,
                    discrepancy_id=str(discrepancy.id),
                    discrepancy_status=discrepancy.status,
                )
            )
            continue
        internal_amount = internal_totals.get(kind)
        checks.append(
            ReconciliationStatementTotalCheck(
                kind=kind,
                status="matched" if run and run.status == ReconciliationRunStatus.COMPLETED else "unknown",
                external_amount=external_amount,
                internal_amount=Decimal(str(internal_amount)) if internal_amount is not None else None,
                delta=Decimal("0") if run and run.status == ReconciliationRunStatus.COMPLETED else None,
            )
        )
    return checks


def _build_statement_explain(db: Session, *, statement: ExternalStatement) -> ExternalStatementExplain:
    run, relation_source = _related_run_for_statement(db, statement=statement)
    discrepancies: list[ReconciliationDiscrepancy] = []
    link_counts = ReconciliationLinkCounts()
    if run is not None:
        discrepancies = _discrepancies_for_statement(db, statement=statement)
        counts = _link_counts_for_run(db, run)
        if counts is not None:
            link_counts = counts
    unmatched_external = sum(
        1 for item in discrepancies if item.discrepancy_type == item.discrepancy_type.UNMATCHED_EXTERNAL
    )
    unmatched_internal = sum(
        1 for item in discrepancies if item.discrepancy_type == item.discrepancy_type.UNMATCHED_INTERNAL
    )
    mismatched_amount = sum(
        1 for item in discrepancies if item.discrepancy_type == item.discrepancy_type.MISMATCHED_AMOUNT
    )
    open_discrepancies = sum(1 for item in discrepancies if item.status == ReconciliationDiscrepancyStatus.OPEN)
    resolved_discrepancies = sum(1 for item in discrepancies if item.status == ReconciliationDiscrepancyStatus.RESOLVED)
    ignored_discrepancies = sum(1 for item in discrepancies if item.status == ReconciliationDiscrepancyStatus.IGNORED)
    adjusted_discrepancies = sum(
        1 for item in discrepancies if isinstance(item.resolution, dict) and item.resolution.get("adjustment_tx_id")
    )
    return ExternalStatementExplain(
        related_run_id=str(run.id) if run is not None else None,
        related_run_status=run.status if run is not None else None,
        relation_source=relation_source,
        line_count=len(statement.lines) if isinstance(statement.lines, list) else 0,
        matched_links=link_counts.matched,
        mismatched_links=link_counts.mismatched,
        pending_links=link_counts.pending,
        unmatched_external=unmatched_external,
        unmatched_internal=unmatched_internal,
        mismatched_amount=mismatched_amount,
        open_discrepancies=open_discrepancies,
        resolved_discrepancies=resolved_discrepancies,
        ignored_discrepancies=ignored_discrepancies,
        adjusted_discrepancies=adjusted_discrepancies,
        total_checks=_statement_total_checks(statement=statement, run=run, discrepancies=discrepancies),
    )


def _discrepancies_for_run(
    db: Session,
    *,
    run_id: str,
    discrepancy_status: str | None = None,
    discrepancy_type: str | None = None,
) -> list[ReconciliationDiscrepancy]:
    query = db.query(ReconciliationDiscrepancy).filter(ReconciliationDiscrepancy.run_id == run_id)
    if discrepancy_status:
        query = query.filter(ReconciliationDiscrepancy.status == _normalize_discrepancy_status_filter(discrepancy_status))
    if discrepancy_type:
        query = query.filter(
            ReconciliationDiscrepancy.discrepancy_type == _normalize_discrepancy_type_filter(discrepancy_type)
        )
    return query.order_by(ReconciliationDiscrepancy.created_at.asc()).all()


def _discrepancies_for_statement(
    db: Session,
    *,
    statement: ExternalStatement,
    discrepancy_status: str | None = None,
    discrepancy_type: str | None = None,
) -> list[ReconciliationDiscrepancy]:
    run, _ = _related_run_for_statement(db, statement=statement)
    if run is None:
        return []
    statement_id = str(statement.id)
    result: list[ReconciliationDiscrepancy] = []
    for item in _discrepancies_for_run(
        db,
        run_id=str(run.id),
        discrepancy_status=discrepancy_status,
        discrepancy_type=discrepancy_type,
    ):
        details = item.details if isinstance(item.details, dict) else {}
        item_statement_id = details.get("statement_id")
        if item_statement_id is not None and str(item_statement_id) != statement_id:
            continue
        result.append(item)
    return result


def _normalize_discrepancy_status_filter(raw: str) -> str:
    normalized = raw.strip()
    if not normalized:
        return normalized
    lowered = normalized.lower()
    try:
        return ReconciliationDiscrepancyStatus(lowered).value
    except ValueError:
        member = ReconciliationDiscrepancyStatus.__members__.get(normalized.upper())
        return member.value if member is not None else lowered


def _normalize_discrepancy_type_filter(raw: str) -> str:
    normalized = raw.strip()
    if not normalized:
        return normalized
    lowered = normalized.lower()
    try:
        return ReconciliationDiscrepancyType(lowered).value
    except ValueError:
        member = ReconciliationDiscrepancyType.__members__.get(normalized.upper())
        return member.value if member is not None else lowered


def _discrepancies_by_entity(
    db: Session,
    *,
    run_id: str,
) -> dict[tuple[str, str], list[ReconciliationDiscrepancy]]:
    rows = (
        db.query(ReconciliationDiscrepancy)
        .filter(ReconciliationDiscrepancy.run_id == run_id)
        .order_by(ReconciliationDiscrepancy.created_at.asc())
        .all()
    )
    result: dict[tuple[str, str], list[ReconciliationDiscrepancy]] = {}
    for item in rows:
        details = item.details if isinstance(item.details, dict) else {}
        entity_type = details.get("entity_type")
        entity_id = details.get("entity_id")
        if entity_type is None or entity_id is None:
            continue
        key = (str(entity_type), str(entity_id))
        result.setdefault(key, []).append(item)
    return result


def _serialize_link(
    item: ReconciliationLink,
    *,
    discrepancies_by_entity: dict[tuple[str, str], list[ReconciliationDiscrepancy]],
) -> ReconciliationLinkResponse:
    linked = discrepancies_by_entity.get((str(item.entity_type), str(item.entity_id)), [])
    review_status = None
    for candidate_status in (
        ReconciliationDiscrepancyStatus.OPEN if linked else None,
        ReconciliationDiscrepancyStatus.RESOLVED if linked else None,
        ReconciliationDiscrepancyStatus.IGNORED if linked else None,
    ):
        if candidate_status is None:
            continue
        if any(entry.status == candidate_status for entry in linked):
            review_status = candidate_status
            break
    return ReconciliationLinkResponse(
        id=str(item.id),
        run_id=str(item.run_id) if item.run_id else None,
        entity_type=item.entity_type,
        entity_id=str(item.entity_id),
        provider=item.provider,
        currency=item.currency,
        expected_amount=item.expected_amount,
        direction=item.direction,
        expected_at=item.expected_at,
        match_key=item.match_key,
        status=item.status,
        created_at=item.created_at,
        discrepancy_ids=[str(entry.id) for entry in linked],
        review_status=review_status,
    )


def _serialize_run(
    run: ReconciliationRun,
    *,
    statement: ReconciliationStatementSummary | None = None,
    timeline: list[ReconciliationAuditEvent] | None = None,
    link_counts: ReconciliationLinkCounts | None = None,
) -> ReconciliationRunResponse:
    return ReconciliationRunResponse(
        id=str(run.id),
        scope=run.scope,
        provider=run.provider,
        period_start=run.period_start,
        period_end=run.period_end,
        status=run.status,
        created_at=run.created_at,
        created_by_user_id=str(run.created_by_user_id) if run.created_by_user_id else None,
        summary=run.summary,
        audit_event_id=str(run.audit_event_id) if run.audit_event_id else None,
        statement=statement,
        timeline=timeline or [],
        link_counts=link_counts,
    )

def _serialize_discrepancy(
    item: ReconciliationDiscrepancy,
    *,
    timeline: list[ReconciliationAuditEvent] | None = None,
    adjustment_explain: ReconciliationAdjustmentExplain | None = None,
) -> ReconciliationDiscrepancyResponse:
    return ReconciliationDiscrepancyResponse(
        id=str(item.id),
        run_id=str(item.run_id),
        ledger_account_id=str(item.ledger_account_id) if item.ledger_account_id else None,
        currency=item.currency,
        discrepancy_type=item.discrepancy_type,
        internal_amount=item.internal_amount,
        external_amount=item.external_amount,
        delta=item.delta,
        details=item.details,
        status=item.status,
        resolution=item.resolution,
        created_at=item.created_at,
        timeline=timeline or [],
        adjustment_explain=adjustment_explain,
    )


def _serialize_statement(
    item: ExternalStatement,
    *,
    explain: ExternalStatementExplain | None = None,
    timeline: list[ReconciliationAuditEvent] | None = None,
) -> ExternalStatementResponse:
    return ExternalStatementResponse(
        id=str(item.id),
        provider=item.provider,
        period_start=item.period_start,
        period_end=item.period_end,
        currency=item.currency,
        total_in=item.total_in,
        total_out=item.total_out,
        closing_balance=item.closing_balance,
        lines=item.lines,
        created_at=item.created_at,
        source_hash=item.source_hash,
        audit_event_id=str(item.audit_event_id) if item.audit_event_id else None,
        explain=explain,
        timeline=timeline or [],
    )
