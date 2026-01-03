from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.config import settings
from app.db import get_db
from app.schemas.admin.bank_stub import (
    BankStubPaymentCreateRequest,
    BankStubPaymentResponse,
    BankStubStatementResponse,
)
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.bank_stub_service import (
    BankStubServiceError,
    create_stub_payment,
    generate_statement,
    get_statement,
    get_stub_payment,
)
from app.security.rbac.guard import require_permission


router = APIRouter(
    prefix="/bank_stub",
    tags=["admin", "bank_stub"],
    dependencies=[Depends(require_permission("admin:billing:*"))],
)


def _require_enabled() -> None:
    if not settings.BANK_STUB_ENABLED:
        raise HTTPException(status_code=404, detail="bank_stub_disabled")


@router.post("/payments", response_model=BankStubPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: BankStubPaymentCreateRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> BankStubPaymentResponse:
    _require_enabled()
    tenant_id = int(token.get("tenant_id") or 0)
    actor = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    try:
        bank_payment, _billing_payment = create_stub_payment(
            db,
            tenant_id=tenant_id,
            invoice_id=payload.invoice_id,
            amount=payload.amount,
            idempotency_key=payload.idempotency_key,
            actor=actor,
        )
        db.commit()
    except BankStubServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BankStubPaymentResponse.model_validate(bank_payment)


@router.get("/payments/{payment_id}", response_model=BankStubPaymentResponse)
def get_payment(payment_id: str, db: Session = Depends(get_db)) -> BankStubPaymentResponse:
    _require_enabled()
    payment = get_stub_payment(db, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="bank_stub_payment_not_found")
    return BankStubPaymentResponse.model_validate(payment)


@router.post("/statements/generate", response_model=BankStubStatementResponse, status_code=201)
def generate_stub_statement(
    request: Request,
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> BankStubStatementResponse:
    _require_enabled()
    if from_dt > to_dt:
        raise HTTPException(status_code=422, detail="invalid_period")
    tenant_id = int(token.get("tenant_id") or 0)
    actor = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    try:
        statement = generate_statement(
            db,
            tenant_id=tenant_id,
            period_from=from_dt,
            period_to=to_dt,
            actor=actor,
        )
        db.commit()
    except BankStubServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BankStubStatementResponse.model_validate(statement)


@router.get("/statements/{statement_id}", response_model=BankStubStatementResponse)
def get_stub_statement(statement_id: str, db: Session = Depends(get_db)) -> BankStubStatementResponse:
    _require_enabled()
    statement = get_statement(db, statement_id)
    if statement is None:
        raise HTTPException(status_code=404, detail="bank_stub_statement_not_found")
    return BankStubStatementResponse.model_validate(statement)
