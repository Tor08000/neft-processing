from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.integrations.hub.artifacts import load_integration_file
from app.integrations.onec.exporter import export_onec_documents
from app.integrations.bank.statements.importer import import_bank_statement
from app.models.integrations import (
    BankReconciliationDiff,
    BankReconciliationMatch,
    BankReconciliationRun,
    BankStatement,
    IntegrationExport,
)
from app.schemas.admin.integrations import (
    BankStatementImportRequest,
    BankStatementListResponse,
    BankStatementResponse,
    BankReconciliationDiffListResponse,
    BankReconciliationDiffResponse,
    BankReconciliationMatchListResponse,
    BankReconciliationMatchResponse,
    BankReconciliationRunListResponse,
    BankReconciliationRunResponse,
    IntegrationExportListResponse,
    IntegrationExportResponse,
    OnecExportRequest,
)
from app.services.audit_service import request_context_from_request
from app.security.rbac.guard import require_permission

router = APIRouter(
    prefix="/integrations",
    tags=["admin", "integrations"],
    dependencies=[Depends(require_permission("admin:integrations:*"))],
)


@router.post("/onec/export", response_model=IntegrationExportResponse, status_code=201)
def create_onec_export(
    payload: OnecExportRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> IntegrationExportResponse:
    if payload.period_start > payload.period_end:
        raise HTTPException(status_code=422, detail="invalid_period")
    actor = request_context_from_request(None, token=token)
    export = export_onec_documents(
        db,
        period_start=payload.period_start,
        period_end=payload.period_end,
        mapping_version=payload.mapping_version,
        seller={"name": payload.seller_name, "inn": payload.seller_inn, "kpp": payload.seller_kpp},
        actor=actor,
    )
    db.commit()
    return _serialize_export(export)


@router.get("/onec/exports", response_model=IntegrationExportListResponse)
def list_onec_exports(db: Session = Depends(get_db)) -> IntegrationExportListResponse:
    exports = (
        db.query(IntegrationExport)
        .order_by(IntegrationExport.created_at.desc())
        .all()
    )
    return IntegrationExportListResponse(exports=[_serialize_export(item) for item in exports])


@router.get("/onec/exports/{export_id}/download")
def download_onec_export(export_id: str, db: Session = Depends(get_db)) -> Response:
    export = db.query(IntegrationExport).filter(IntegrationExport.id == export_id).one_or_none()
    if not export or not export.file_id:
        raise HTTPException(status_code=404, detail="export_not_found")
    file_record = load_integration_file(db, export.file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="file_not_found")
    return Response(
        content=file_record.payload,
        media_type=file_record.content_type,
        headers={"Content-Disposition": f"attachment; filename={file_record.file_name}"},
    )


@router.post("/bank/statements/import", response_model=BankStatementResponse, status_code=201)
def import_statement(
    payload: BankStatementImportRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> BankStatementResponse:
    if payload.period_start > payload.period_end:
        raise HTTPException(status_code=422, detail="invalid_period")
    actor = request_context_from_request(None, token=token)
    statement = import_bank_statement(
        db,
        bank_code=payload.bank_code,
        period_start=payload.period_start,
        period_end=payload.period_end,
        file_name=payload.file_name,
        content_type=payload.content_type,
        payload=payload.content.encode("utf-8"),
        actor=actor,
    )
    db.commit()
    return _serialize_statement(statement)


@router.get("/bank/statements", response_model=BankStatementListResponse)
def list_statements(db: Session = Depends(get_db)) -> BankStatementListResponse:
    statements = db.query(BankStatement).order_by(BankStatement.created_at.desc()).all()
    return BankStatementListResponse(statements=[_serialize_statement(item) for item in statements])


@router.get("/bank/reconciliation/runs", response_model=BankReconciliationRunListResponse)
def list_bank_reconciliation_runs(db: Session = Depends(get_db)) -> BankReconciliationRunListResponse:
    runs = db.query(BankReconciliationRun).order_by(BankReconciliationRun.created_at.desc()).all()
    return BankReconciliationRunListResponse(runs=[_serialize_run(item) for item in runs])


@router.get("/bank/reconciliation/runs/{run_id}/diffs", response_model=BankReconciliationDiffListResponse)
def list_bank_reconciliation_diffs(run_id: str, db: Session = Depends(get_db)) -> BankReconciliationDiffListResponse:
    diffs = (
        db.query(BankReconciliationDiff)
        .filter(BankReconciliationDiff.run_id == run_id)
        .order_by(BankReconciliationDiff.created_at.asc())
        .all()
    )
    return BankReconciliationDiffListResponse(diffs=[_serialize_diff(item) for item in diffs])


@router.get("/bank/reconciliation/runs/{run_id}/matches", response_model=BankReconciliationMatchListResponse)
def list_bank_reconciliation_matches(
    run_id: str, db: Session = Depends(get_db)
) -> BankReconciliationMatchListResponse:
    matches = (
        db.query(BankReconciliationMatch)
        .filter(BankReconciliationMatch.run_id == run_id)
        .order_by(BankReconciliationMatch.created_at.asc())
        .all()
    )
    return BankReconciliationMatchListResponse(matches=[_serialize_match(item) for item in matches])


def _serialize_export(export: IntegrationExport) -> IntegrationExportResponse:
    return IntegrationExportResponse(
        id=str(export.id),
        integration_type=export.integration_type,
        entity_type=export.entity_type,
        period_start=export.period_start,
        period_end=export.period_end,
        status=export.status,
        file_id=str(export.file_id) if export.file_id else None,
        created_at=export.created_at,
    )


def _serialize_statement(statement: BankStatement) -> BankStatementResponse:
    return BankStatementResponse(
        id=str(statement.id),
        bank_code=statement.bank_code,
        period_start=statement.period_start,
        period_end=statement.period_end,
        status=statement.status,
        file_id=str(statement.file_id) if statement.file_id else None,
        created_at=statement.created_at,
    )


def _serialize_run(run: BankReconciliationRun) -> BankReconciliationRunResponse:
    return BankReconciliationRunResponse(
        id=str(run.id),
        statement_id=str(run.statement_id),
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
    )


def _serialize_diff(diff: BankReconciliationDiff) -> BankReconciliationDiffResponse:
    return BankReconciliationDiffResponse(
        id=str(diff.id),
        run_id=str(diff.run_id),
        source=diff.source,
        tx_id=str(diff.tx_id),
        reason=diff.reason,
        created_at=diff.created_at,
    )


def _serialize_match(match: BankReconciliationMatch) -> BankReconciliationMatchResponse:
    return BankReconciliationMatchResponse(
        id=str(match.id),
        run_id=str(match.run_id),
        bank_tx_id=str(match.bank_tx_id),
        invoice_id=str(match.invoice_id) if match.invoice_id else None,
        match_type=match.match_type,
        score=match.score,
        created_at=match.created_at,
    )


__all__ = ["router"]
