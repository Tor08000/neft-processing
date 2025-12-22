from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.finance import CreditNoteStatus, PaymentStatus
from app.schemas.admin.finance import (
    CreditNoteRequest,
    CreditNoteResponse,
    PaymentRequest,
    PaymentResponse,
)
from app.services.finance import FinanceOperationInProgress, FinanceService, InvoiceNotFound
from app.services.job_locks import make_stable_key

router = APIRouter(prefix="/finance", tags=["admin"])


@router.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(body: PaymentRequest, db: Session = Depends(get_db)) -> PaymentResponse:
    service = FinanceService(db)
    scope_key = make_stable_key(
        "finance_payment",
        {"invoice_id": body.invoice_id, "amount": body.amount, "currency": body.currency},
        body.idempotency_key,
    )
    try:
        result = service.apply_payment(
            invoice_id=body.invoice_id,
            amount=body.amount,
            currency=body.currency,
            idempotency_key=scope_key,
        )
    except InvoiceNotFound as exc:
        raise HTTPException(status_code=404, detail="invoice not found") from exc
    except FinanceOperationInProgress as exc:
        raise HTTPException(status_code=409, detail="already running") from exc

    return PaymentResponse(
        payment_id=str(result.payment.id),
        invoice_id=result.payment.invoice_id,
        amount=result.payment.amount,
        currency=result.payment.currency,
        due_amount=result.invoice.amount_due,
        invoice_status=result.invoice.status,
        status=result.payment.status or PaymentStatus.POSTED,
        created_at=result.payment.created_at,
    )


@router.post("/credit-notes", response_model=CreditNoteResponse, status_code=201)
def create_credit_note(body: CreditNoteRequest, db: Session = Depends(get_db)) -> CreditNoteResponse:
    service = FinanceService(db)
    scope_key = make_stable_key(
        "finance_credit_note",
        {"invoice_id": body.invoice_id, "amount": body.amount, "currency": body.currency, "reason": body.reason or ""},
        body.idempotency_key,
    )
    try:
        result = service.create_credit_note(
            invoice_id=body.invoice_id,
            amount=body.amount,
            currency=body.currency,
            reason=body.reason,
            idempotency_key=scope_key,
        )
    except InvoiceNotFound as exc:
        raise HTTPException(status_code=404, detail="invoice not found") from exc
    except FinanceOperationInProgress as exc:
        raise HTTPException(status_code=409, detail="already running") from exc

    return CreditNoteResponse(
        credit_note_id=str(result.credit_note.id),
        invoice_id=result.credit_note.invoice_id,
        amount=result.credit_note.amount,
        currency=result.credit_note.currency,
        due_amount=result.invoice.amount_due,
        invoice_status=result.invoice.status,
        status=result.credit_note.status or CreditNoteStatus.POSTED,
        created_at=result.credit_note.created_at,
    )


__all__ = ["router"]
