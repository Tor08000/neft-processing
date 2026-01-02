from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
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
