from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.finance import CreditNoteStatus, PaymentStatus
from app.schemas.admin.finance import (
    CreditNoteRequest,
    CreditNoteResponse,
    PaymentRequest,
    PaymentResponse,
)
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.finance import FinanceOperationInProgress, FinanceService, InvoiceNotFound
from app.services.invoice_state_machine import InvalidTransitionError, InvoiceInvariantError
from app.services.job_locks import make_stable_key

router = APIRouter(prefix="/finance", tags=["admin"])


@router.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(
    body: PaymentRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> PaymentResponse:
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
    except InvalidTransitionError as exc:
        AuditService(db).audit(
            event_type="PAYMENT_CONFLICT",
            entity_type="invoice",
            entity_id=body.invoice_id,
            action="PAYMENT_DENIED",
            reason=str(exc),
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvoiceInvariantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    AuditService(db).audit(
        event_type="PAYMENT_POSTED",
        entity_type="payment",
        entity_id=str(result.payment.id),
        action="CREATE",
        after={
            "invoice_id": result.payment.invoice_id,
            "amount": result.payment.amount,
            "currency": result.payment.currency,
            "status": result.payment.status.value if result.payment.status else None,
            "invoice_status": result.invoice.status.value if result.invoice.status else None,
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
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
def create_credit_note(
    body: CreditNoteRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CreditNoteResponse:
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
    except InvalidTransitionError as exc:
        AuditService(db).audit(
            event_type="CREDIT_NOTE_CONFLICT",
            entity_type="invoice",
            entity_id=body.invoice_id,
            action="CREDIT_NOTE_DENIED",
            reason=str(exc),
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvoiceInvariantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    AuditService(db).audit(
        event_type="CREDIT_NOTE_CREATED",
        entity_type="credit_note",
        entity_id=str(result.credit_note.id),
        action="CREATE",
        after={
            "invoice_id": result.credit_note.invoice_id,
            "amount": result.credit_note.amount,
            "currency": result.credit_note.currency,
            "status": result.credit_note.status.value if result.credit_note.status else None,
            "invoice_status": result.invoice.status.value if result.invoice.status else None,
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
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
