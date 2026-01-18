from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.config import settings
from app.db import get_db
from app.db.types import new_uuid_str
from app.models.reconciliation import ExternalStatement, ReconciliationDiscrepancy, ReconciliationRun
from app.schemas.admin.reconciliation import (
    ExternalStatementListResponse,
    ExternalStatementResponse,
    ExternalStatementUploadRequest,
    IgnoreDiscrepancyRequest,
    ReconciliationDiscrepancyListResponse,
    ReconciliationDiscrepancyResponse,
    ReconciliationExternalRunRequest,
    ReconciliationRunCreateRequest,
    ReconciliationRunListResponse,
    ReconciliationRunResponse,
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


@router.get("/runs/{run_id}/discrepancies", response_model=ReconciliationDiscrepancyListResponse)
def list_discrepancies(run_id: str, db: Session = Depends(get_db)) -> ReconciliationDiscrepancyListResponse:
    discrepancies = (
        db.query(ReconciliationDiscrepancy)
        .filter(ReconciliationDiscrepancy.run_id == run_id)
        .order_by(ReconciliationDiscrepancy.created_at.asc())
        .all()
    )
    return ReconciliationDiscrepancyListResponse(
        discrepancies=[_serialize_discrepancy(item) for item in discrepancies]
    )


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


def _serialize_run(run: ReconciliationRun) -> ReconciliationRunResponse:
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
    )


def _serialize_discrepancy(item: ReconciliationDiscrepancy) -> ReconciliationDiscrepancyResponse:
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
    )


def _serialize_statement(item: ExternalStatement) -> ExternalStatementResponse:
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
    )
