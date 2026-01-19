from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.schemas.admin.reconciliation_imports import (
    BankStatementImportCompleteRequest,
    BankStatementImportCreateRequest,
    BankStatementImportCreateResponse,
    BankStatementImportListResponse,
    BankStatementImportRead,
    BankStatementImportActionRequest,
    BankStatementTransactionApplyRequest,
    BankStatementTransactionIgnoreRequest,
    BankStatementTransactionListResponse,
)
from app.db.types import new_uuid_str
from app.models.audit_log import AuditVisibility
from app.services.audit_service import (
    AuditService,
    _sanitize_token_for_audit,
    request_context_from_request,
)
from app.services.bank_statement_import_storage import BankStatementImportStorage
from app.services.bank_statement_reconciliation import (
    apply_matches,
    apply_transaction_to_invoice,
    create_import_record,
    get_import,
    ignore_transaction,
    list_imports,
    list_transactions,
    mark_import_status,
    match_transactions,
    parse_statement_import,
)
from app.security.rbac.guard import require_permission

router = APIRouter(
    prefix="/reconciliation",
    tags=["admin", "reconciliation"],
    dependencies=[Depends(require_permission("admin:reconciliation:*"))],
)


@router.post("/imports", response_model=BankStatementImportCreateResponse, status_code=201)
def create_import(
    payload: BankStatementImportCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> BankStatementImportCreateResponse:
    storage = BankStatementImportStorage()
    import_id = new_uuid_str()
    object_key = storage.build_object_key(import_id=import_id, file_name=payload.file_name)
    upload_url = storage.presign_upload(
        object_key=object_key,
        content_type=payload.content_type,
        expires=3600,
    )
    if not upload_url:
        raise HTTPException(status_code=500, detail="upload_url_error")

    period_from = datetime.combine(payload.period_from, datetime.min.time()) if payload.period_from else None
    period_to = datetime.combine(payload.period_to, datetime.min.time()) if payload.period_to else None
    record = create_import_record(
        db,
        import_id=import_id,
        admin_id=token.get("user_id") or token.get("sub"),
        file_object_key=object_key,
        fmt=payload.format,
        period_from=period_from,
        period_to=period_to,
    )
    AuditService(db).audit(
        event_type="bank_statement_imported",
        entity_type="bank_statement_import",
        entity_id=str(record["id"]),
        action="IMPORT",
        visibility=AuditVisibility.INTERNAL,
        after={"file_object_key": object_key, "format": payload.format},
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    db.commit()

    return BankStatementImportCreateResponse(
        import_id=str(record["id"]),
        upload_url=upload_url,
        object_key=object_key,
    )


@router.post("/imports/{import_id}/complete", response_model=BankStatementImportRead)
def complete_import(
    import_id: str,
    payload: BankStatementImportCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> BankStatementImportRead:
    record = get_import(db, import_id=import_id)
    if not record:
        raise HTTPException(status_code=404, detail="import_not_found")
    if payload.object_key != record["file_object_key"]:
        raise HTTPException(status_code=422, detail="object_key_mismatch")

    storage = BankStatementImportStorage()
    payload_bytes = storage.fetch_bytes(object_key=payload.object_key)
    if not payload_bytes:
        mark_import_status(db, import_id=import_id, status="FAILED", error="file_missing")
        db.commit()
        raise HTTPException(status_code=404, detail="file_missing")

    actor = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    try:
        parse_statement_import(
            db,
            import_id=import_id,
            payload=payload_bytes,
            fmt=record.get("format"),
            actor=actor,
        )
        match_transactions(db, import_id=import_id, actor=actor)
        apply_matches(db, import_id=import_id, actor=actor)
    except Exception as exc:  # noqa: BLE001 - surface parse errors
        mark_import_status(db, import_id=import_id, status="FAILED", error=str(exc))
        db.commit()
        raise HTTPException(status_code=400, detail="parse_failed") from exc

    updated = mark_import_status(db, import_id=import_id, status="PARSED")
    db.commit()
    if not updated:
        raise HTTPException(status_code=404, detail="import_not_found")
    return BankStatementImportRead.model_validate(updated)


@router.post("/imports/{import_id}/parse", response_model=BankStatementImportRead)
def parse_import(
    import_id: str,
    payload: BankStatementImportActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> BankStatementImportRead:
    record = get_import(db, import_id=import_id)
    if not record:
        raise HTTPException(status_code=404, detail="import_not_found")
    storage = BankStatementImportStorage()
    payload_bytes = storage.fetch_bytes(object_key=record.get("file_object_key"))
    if not payload_bytes:
        mark_import_status(db, import_id=import_id, status="FAILED", error="file_missing")
        db.commit()
        raise HTTPException(status_code=404, detail="file_missing")
    actor = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    try:
        parse_statement_import(
            db,
            import_id=import_id,
            payload=payload_bytes,
            fmt=record.get("format"),
            actor=actor,
        )
    except Exception as exc:  # noqa: BLE001
        mark_import_status(db, import_id=import_id, status="FAILED", error=str(exc))
        db.commit()
        raise HTTPException(status_code=400, detail="parse_failed") from exc
    AuditService(db).audit(
        event_type="bank_statement_parsed",
        entity_type="bank_statement_import",
        entity_id=str(import_id),
        action="PARSE",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.reason,
        request_ctx=actor,
    )
    updated = mark_import_status(db, import_id=import_id, status="PARSED")
    db.commit()
    if not updated:
        raise HTTPException(status_code=404, detail="import_not_found")
    return BankStatementImportRead.model_validate(updated)


@router.post("/imports/{import_id}/match", response_model=BankStatementImportRead)
def match_import(
    import_id: str,
    payload: BankStatementImportActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> BankStatementImportRead:
    record = get_import(db, import_id=import_id)
    if not record:
        raise HTTPException(status_code=404, detail="import_not_found")
    actor = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    match_transactions(db, import_id=import_id, actor=actor)
    apply_matches(db, import_id=import_id, actor=actor)
    AuditService(db).audit(
        event_type="bank_statement_matched",
        entity_type="bank_statement_import",
        entity_id=str(import_id),
        action="MATCH",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.reason,
        request_ctx=actor,
    )
    updated = mark_import_status(db, import_id=import_id, status="MATCHED")
    db.commit()
    if not updated:
        raise HTTPException(status_code=404, detail="import_not_found")
    return BankStatementImportRead.model_validate(updated)


@router.get("/imports", response_model=BankStatementImportListResponse)
def list_imports_view(db: Session = Depends(get_db)) -> BankStatementImportListResponse:
    items = list_imports(db)
    return BankStatementImportListResponse(items=[BankStatementImportRead.model_validate(item) for item in items])


@router.get("/imports/{import_id}", response_model=BankStatementImportRead)
def get_import_view(import_id: str, db: Session = Depends(get_db)) -> BankStatementImportRead:
    record = get_import(db, import_id=import_id)
    if not record:
        raise HTTPException(status_code=404, detail="import_not_found")
    return BankStatementImportRead.model_validate(record)


@router.get("/transactions", response_model=BankStatementTransactionListResponse)
def list_transactions_view(
    import_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> BankStatementTransactionListResponse:
    items = list_transactions(db, import_id=import_id, status=status)
    return BankStatementTransactionListResponse(items=items)


@router.post("/transactions/{transaction_id}/apply")
def apply_transaction(
    transaction_id: str,
    payload: BankStatementTransactionApplyRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    actor = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    intake = apply_transaction_to_invoice(
        db,
        transaction_id=transaction_id,
        invoice_id=payload.invoice_id,
        actor=actor,
        reason=payload.reason,
    )
    if not intake:
        raise HTTPException(status_code=404, detail="transaction_not_found")
    db.commit()
    return {"status": "ok", "payment_intake_id": intake["id"]}


@router.post("/transactions/{transaction_id}/ignore")
def ignore_transaction_view(
    transaction_id: str,
    payload: BankStatementTransactionIgnoreRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    actor = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    if not ignore_transaction(db, transaction_id=transaction_id, actor=actor, reason=payload.reason):
        raise HTTPException(status_code=404, detail="transaction_not_found")
    db.commit()
    return {"status": "ok"}
