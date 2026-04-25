from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.billing_flow import BillingInvoice, BillingInvoiceStatus, BillingPayment, BillingRefund
from app.schemas.admin.billing_flows import (
    BillingInvoiceIssueRequest,
    BillingInvoiceListResponse,
    BillingInvoiceResponse,
    BillingPaymentCaptureRequest,
    BillingPaymentResponse,
    BillingPaymentsListResponse,
    BillingRefundRequest,
    BillingRefundResponse,
)
from app.services.billing_service import capture_payment, issue_invoice, refund_payment
from app.services.case_events_service import CaseEventActor
from app.services.token_claims import DEFAULT_TENANT_ID, resolve_token_tenant_id


# Canonical admin owner for explicit invoice/payment/refund flow actions over billing_flow storage.
# Distinct from admin/billing summary/tariff control-plane reads.
router = APIRouter(prefix="/billing/flows", tags=["admin"])


def _actor_from_token(token: dict) -> CaseEventActor:
    return CaseEventActor(
        id=token.get("user_id") or token.get("sub"),
        email=token.get("email"),
    )


@router.post("/invoices", response_model=BillingInvoiceResponse, status_code=status.HTTP_201_CREATED)
def issue_invoice_endpoint(
    payload: BillingInvoiceIssueRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> BillingInvoiceResponse:
    tenant_id = resolve_token_tenant_id(token, default=DEFAULT_TENANT_ID)
    actor = _actor_from_token(token)
    try:
        result = issue_invoice(
            db,
            tenant_id=tenant_id,
            client_id=payload.client_id,
            case_id=payload.case_id,
            currency=payload.currency,
            amount_total=payload.amount_total,
            due_at=payload.due_at,
            idempotency_key=payload.idempotency_key,
            actor=actor,
            request_id=request.headers.get("x-request-id"),
            trace_id=request.headers.get("x-trace-id"),
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    invoice = result.invoice
    return BillingInvoiceResponse(
        id=str(invoice.id),
        invoice_number=invoice.invoice_number,
        client_id=str(invoice.client_id),
        case_id=str(invoice.case_id) if invoice.case_id else None,
        currency=invoice.currency,
        amount_total=invoice.amount_total,
        amount_paid=invoice.amount_paid,
        status=invoice.status,
        issued_at=invoice.issued_at,
        due_at=invoice.due_at,
        ledger_tx_id=str(invoice.ledger_tx_id),
        audit_event_id=str(invoice.audit_event_id),
        created_at=invoice.created_at,
    )


@router.post("/invoices/{invoice_id}/capture", response_model=BillingPaymentResponse, status_code=201)
def capture_payment_endpoint(
    invoice_id: str,
    payload: BillingPaymentCaptureRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> BillingPaymentResponse:
    tenant_id = resolve_token_tenant_id(token, default=DEFAULT_TENANT_ID)
    actor = _actor_from_token(token)
    try:
        result = capture_payment(
            db,
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            provider=payload.provider,
            provider_payment_id=payload.provider_payment_id,
            amount=payload.amount,
            currency=payload.currency,
            idempotency_key=payload.idempotency_key,
            actor=actor,
            request_id=request.headers.get("x-request-id"),
            trace_id=request.headers.get("x-trace-id"),
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payment = result.payment
    return BillingPaymentResponse(
        id=str(payment.id),
        invoice_id=str(payment.invoice_id),
        provider=payment.provider,
        provider_payment_id=payment.provider_payment_id,
        currency=payment.currency,
        amount=payment.amount,
        captured_at=payment.captured_at,
        status=payment.status,
        ledger_tx_id=str(payment.ledger_tx_id),
        audit_event_id=str(payment.audit_event_id),
        created_at=payment.created_at,
    )


@router.post("/payments/{payment_id}/refund", response_model=BillingRefundResponse, status_code=201)
def refund_payment_endpoint(
    payment_id: str,
    payload: BillingRefundRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> BillingRefundResponse:
    tenant_id = resolve_token_tenant_id(token, default=DEFAULT_TENANT_ID)
    actor = _actor_from_token(token)
    try:
        result = refund_payment(
            db,
            tenant_id=tenant_id,
            payment_id=payment_id,
            provider_refund_id=payload.provider_refund_id,
            amount=payload.amount,
            currency=payload.currency,
            idempotency_key=payload.idempotency_key,
            actor=actor,
            request_id=request.headers.get("x-request-id"),
            trace_id=request.headers.get("x-trace-id"),
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    refund = result.refund
    return BillingRefundResponse(
        id=str(refund.id),
        payment_id=str(refund.payment_id),
        provider_refund_id=refund.provider_refund_id,
        currency=refund.currency,
        amount=refund.amount,
        refunded_at=refund.refunded_at,
        status=refund.status,
        ledger_tx_id=str(refund.ledger_tx_id),
        audit_event_id=str(refund.audit_event_id),
        created_at=refund.created_at,
    )


@router.get("/invoices", response_model=BillingInvoiceListResponse)
def list_invoices_endpoint(
    client_id: str | None = Query(None),
    status: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> BillingInvoiceListResponse:
    query = db.query(BillingInvoice)
    if client_id:
        query = query.filter(BillingInvoice.client_id == client_id)
    if status:
        try:
            parsed_status = BillingInvoiceStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid_status") from exc
        query = query.filter(BillingInvoice.status == parsed_status)
    if date_from:
        query = query.filter(BillingInvoice.issued_at >= date_from)
    if date_to:
        query = query.filter(BillingInvoice.issued_at <= date_to)
    total = query.count()
    items = (
        query.order_by(BillingInvoice.issued_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return BillingInvoiceListResponse(
        items=[
            BillingInvoiceResponse(
                id=str(invoice.id),
                invoice_number=invoice.invoice_number,
                client_id=str(invoice.client_id),
                case_id=str(invoice.case_id) if invoice.case_id else None,
                currency=invoice.currency,
                amount_total=invoice.amount_total,
                amount_paid=invoice.amount_paid,
                status=invoice.status,
                issued_at=invoice.issued_at,
                due_at=invoice.due_at,
                ledger_tx_id=str(invoice.ledger_tx_id),
                audit_event_id=str(invoice.audit_event_id),
                created_at=invoice.created_at,
            )
            for invoice in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/invoices/{invoice_id}", response_model=BillingInvoiceResponse)
def get_invoice_endpoint(invoice_id: str, db: Session = Depends(get_db)) -> BillingInvoiceResponse:
    invoice = db.query(BillingInvoice).filter(BillingInvoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    return BillingInvoiceResponse(
        id=str(invoice.id),
        invoice_number=invoice.invoice_number,
        client_id=str(invoice.client_id),
        case_id=str(invoice.case_id) if invoice.case_id else None,
        currency=invoice.currency,
        amount_total=invoice.amount_total,
        amount_paid=invoice.amount_paid,
        status=invoice.status,
        issued_at=invoice.issued_at,
        due_at=invoice.due_at,
        ledger_tx_id=str(invoice.ledger_tx_id),
        audit_event_id=str(invoice.audit_event_id),
        created_at=invoice.created_at,
    )


@router.get("/invoices/{invoice_id}/payments", response_model=BillingPaymentsListResponse)
def list_invoice_payments(
    invoice_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> BillingPaymentsListResponse:
    query = db.query(BillingPayment).filter(BillingPayment.invoice_id == invoice_id)
    total = query.count()
    payments = query.order_by(BillingPayment.captured_at.desc()).offset(offset).limit(limit).all()
    return BillingPaymentsListResponse(
        items=[
            BillingPaymentResponse(
                id=str(payment.id),
                invoice_id=str(payment.invoice_id),
                provider=payment.provider,
                provider_payment_id=payment.provider_payment_id,
                currency=payment.currency,
                amount=payment.amount,
                captured_at=payment.captured_at,
                status=payment.status,
                ledger_tx_id=str(payment.ledger_tx_id),
                audit_event_id=str(payment.audit_event_id),
                created_at=payment.created_at,
            )
            for payment in payments
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/payments/{payment_id}", response_model=BillingPaymentResponse)
def get_payment_endpoint(payment_id: str, db: Session = Depends(get_db)) -> BillingPaymentResponse:
    payment = db.query(BillingPayment).filter(BillingPayment.id == payment_id).one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="payment_not_found")
    return BillingPaymentResponse(
        id=str(payment.id),
        invoice_id=str(payment.invoice_id),
        provider=payment.provider,
        provider_payment_id=payment.provider_payment_id,
        currency=payment.currency,
        amount=payment.amount,
        captured_at=payment.captured_at,
        status=payment.status,
        ledger_tx_id=str(payment.ledger_tx_id),
        audit_event_id=str(payment.audit_event_id),
        created_at=payment.created_at,
    )
