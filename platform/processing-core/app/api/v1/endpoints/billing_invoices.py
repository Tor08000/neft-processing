from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.models.audit_log import ActorType, AuditVisibility
from app.models.finance import CreditNote
from app.models.invoice import Invoice
from app.schemas.billing_invoices import (
    ClosePeriodRequest,
    ClosePeriodResponse,
    InvoiceGenerateResponse,
    InvoiceOut,
    InvoicePaymentRequest,
    InvoicePaymentResponse,
    InvoiceRefundList,
    InvoiceRefundOut,
    InvoiceRefundRequest,
    InvoiceRefundResponse,
)
from app.services.audit_service import AuditService, request_context_from_request
from app.services.billing_invoice_service import close_clearing_period, generate_invoice_for_batch
from app.services.billing_metrics import metrics as billing_metrics
from app.services.finance import (
    FinanceOperationInProgress,
    FinanceService,
    InvoiceNotFound,
    PaymentReferenceConflict,
    RefundReferenceConflict,
)
from app.services.invoice_state_machine import InvalidTransitionError, InvoiceInvariantError
from app.services.job_locks import make_stable_key
from app.services.s3_storage import S3Storage

router = APIRouter(prefix="/api/v1", tags=["billing"])


@router.post("/billing/close-period", response_model=ClosePeriodResponse)
def close_period_endpoint(payload: ClosePeriodRequest, db: Session = Depends(get_db)) -> ClosePeriodResponse:
    try:
        batch = close_clearing_period(
            db,
            date_from=payload.date_from,
            date_to=payload.date_to,
            tenant_id=payload.tenant_id,
        )
    except ValueError as exc:
        if str(exc) == "invalid_period":
            raise HTTPException(status_code=422, detail="invalid period") from exc
        raise
    return ClosePeriodResponse(
        batch_id=batch.id,
        txn_count=batch.operations_count,
        total_amount=batch.total_amount,
        total_qty=batch.total_qty,
    )


@router.post("/invoices/generate", response_model=InvoiceGenerateResponse)
def generate_invoice_endpoint(
    batch_id: str = Query(...),
    request: Request,
    db: Session = Depends(get_db),
) -> InvoiceGenerateResponse:
    run_pdf_sync = os.getenv("DISABLE_CELERY", "0") == "1"
    try:
        result = generate_invoice_for_batch(db, batch_id=batch_id, run_pdf_sync=run_pdf_sync)
    except ValueError as exc:
        if str(exc) == "batch_not_found":
            raise HTTPException(status_code=404, detail="batch not found") from exc
        raise

    invoice = result.invoice
    audit_service = AuditService(db)
    audit_ctx = request_context_from_request(request, actor_type=ActorType.SYSTEM)
    audit_service.audit(
        event_type="INVOICE_CREATED" if result.created else "INVOICE_GENERATED",
        entity_type="invoice",
        entity_id=invoice.id,
        action="CREATE" if result.created else "IDEMPOTENT_REPLAY",
        visibility=AuditVisibility.PUBLIC,
        after={
            "status": invoice.status.value,
            "total_amount": invoice.total_amount,
            "total_with_tax": invoice.total_with_tax,
            "currency": invoice.currency,
            "pdf_status": invoice.pdf_status.value if invoice.pdf_status else None,
        },
        request_ctx=audit_ctx,
    )

    return InvoiceGenerateResponse(
        invoice_id=invoice.id,
        state=invoice.status.value,
        pdf_url=invoice.pdf_url,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice_endpoint(invoice_id: str, db: Session = Depends(get_db)) -> InvoiceOut:
    invoice = db.query(Invoice).filter_by(id=invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    return InvoiceOut(
        id=invoice.id,
        batch_id=invoice.clearing_batch_id,
        number=invoice.number or invoice.external_number,
        amount=invoice.total_amount,
        vat=invoice.tax_amount,
        state=invoice.status.value,
        pdf_url=invoice.pdf_url,
        pdf_object_key=invoice.pdf_object_key,
        issued_at=invoice.issued_at,
    )


@router.post("/invoices/{invoice_id}/payments", response_model=InvoicePaymentResponse, status_code=201)
def create_invoice_payment(
    invoice_id: str,
    payload: InvoicePaymentRequest,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> InvoicePaymentResponse:
    invoice = db.query(Invoice).filter_by(id=invoice_id).one_or_none()
    if invoice is None:
        billing_metrics.mark_payment_error()
        billing_metrics.mark_payment_failed()
        raise HTTPException(status_code=404, detail="invoice not found")

    client_id = token.get("client_id")
    if not client_id or str(invoice.client_id) != str(client_id):
        billing_metrics.mark_payment_error()
        billing_metrics.mark_payment_failed()
        raise HTTPException(status_code=403, detail="forbidden")

    service = FinanceService(db)
    try:
        idempotency_key = make_stable_key(
            "invoice_payment",
            {"external_ref": payload.external_ref, "provider": payload.provider},
        )
        result = service.apply_payment(
            invoice_id=invoice_id,
            amount=payload.amount,
            currency=invoice.currency,
            idempotency_key=idempotency_key,
            external_ref=payload.external_ref,
            provider=payload.provider,
            request_ctx=request_context_from_request(request, token=token),
        )
    except InvoiceNotFound as exc:
        raise HTTPException(status_code=404, detail="invoice not found") from exc
    except PaymentReferenceConflict as exc:
        raise HTTPException(status_code=409, detail="payment reference conflict") from exc
    except FinanceOperationInProgress as exc:
        raise HTTPException(status_code=409, detail="already running") from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvoiceInvariantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_ctx = request_context_from_request(request, token=token)
    event_type = "PAYMENT_IDEMPOTENT_REPLAY" if result.is_replay else "PAYMENT_POSTED"
    action = "IDEMPOTENT_REPLAY" if result.is_replay else "CREATE"
    AuditService(db).audit(
        event_type=event_type,
        entity_type="payment",
        entity_id=str(result.payment.id),
        action=action,
        visibility=AuditVisibility.PUBLIC if event_type == "PAYMENT_POSTED" else AuditVisibility.INTERNAL,
        after={
            "invoice_id": result.payment.invoice_id,
            "amount": result.payment.amount,
            "currency": result.payment.currency,
            "status": result.payment.status.value if result.payment.status else None,
            "invoice_status": result.invoice.status.value if result.invoice.status else None,
        },
        external_refs={
            "provider": payload.provider,
            "external_ref": payload.external_ref,
        }
        if payload.external_ref or payload.provider
        else None,
        request_ctx=audit_ctx,
    )

    return InvoicePaymentResponse(
        payment_id=str(result.payment.id),
        invoice_id=result.payment.invoice_id,
        amount=result.payment.amount,
        currency=result.payment.currency,
        due_amount=result.invoice.amount_due,
        invoice_status=result.invoice.status.value,
        status=result.payment.status.value if result.payment.status else "POSTED",
    )


@router.post("/invoices/{invoice_id}/refunds", response_model=InvoiceRefundResponse, status_code=201)
def create_invoice_refund(
    invoice_id: str,
    payload: InvoiceRefundRequest,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> InvoiceRefundResponse:
    invoice = db.query(Invoice).filter_by(id=invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    client_id = token.get("client_id")
    if not client_id or str(invoice.client_id) != str(client_id):
        raise HTTPException(status_code=403, detail="forbidden")

    service = FinanceService(db)
    try:
        result = service.create_refund(
            invoice_id=invoice_id,
            amount=payload.amount,
            currency=invoice.currency,
            reason=payload.reason,
            external_ref=payload.external_ref,
            provider=payload.provider,
            request_ctx=request_context_from_request(request, token=token),
        )
    except InvoiceNotFound as exc:
        raise HTTPException(status_code=404, detail="invoice not found") from exc
    except RefundReferenceConflict as exc:
        raise HTTPException(status_code=409, detail="refund reference conflict") from exc
    except FinanceOperationInProgress as exc:
        raise HTTPException(status_code=409, detail="already running") from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvoiceInvariantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_ctx = request_context_from_request(request, token=token)
    event_type = "REFUND_IDEMPOTENT_REPLAY" if result.is_replay else "REFUND_POSTED"
    action = "IDEMPOTENT_REPLAY" if result.is_replay else "CREATE"
    AuditService(db).audit(
        event_type=event_type,
        entity_type="refund",
        entity_id=str(result.credit_note.id),
        action=action,
        visibility=AuditVisibility.PUBLIC if event_type == "REFUND_POSTED" else AuditVisibility.INTERNAL,
        after={
            "invoice_id": result.credit_note.invoice_id,
            "amount": result.credit_note.amount,
            "currency": result.credit_note.currency,
            "status": result.credit_note.status.value if result.credit_note.status else None,
            "invoice_status": result.invoice.status.value if result.invoice.status else None,
        },
        external_refs={
            "provider": payload.provider,
            "external_ref": payload.external_ref,
        }
        if payload.external_ref or payload.provider
        else None,
        request_ctx=audit_ctx,
    )

    return InvoiceRefundResponse(
        refund_id=str(result.credit_note.id),
        invoice_id=result.credit_note.invoice_id,
        status=result.credit_note.status.value if result.credit_note.status else "POSTED",
        amount=result.credit_note.amount,
        amount_refunded_total=result.invoice.amount_refunded,
        invoice_state=result.invoice.status.value,
    )


@router.get("/invoices/{invoice_id}/refunds", response_model=InvoiceRefundList)
def list_invoice_refunds(
    invoice_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> InvoiceRefundList:
    invoice = db.query(Invoice).filter_by(id=invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    client_id = token.get("client_id")
    if not client_id or str(invoice.client_id) != str(client_id):
        raise HTTPException(status_code=403, detail="forbidden")

    refunds = (
        db.query(CreditNote)
        .filter(CreditNote.invoice_id == invoice_id)
        .order_by(CreditNote.created_at.asc())
        .all()
    )
    items = [
        InvoiceRefundOut(
            refund_id=str(refund.id),
            invoice_id=refund.invoice_id,
            amount=refund.amount,
            currency=refund.currency,
            provider=refund.provider,
            external_ref=refund.external_ref,
            reason=refund.reason,
            status=refund.status.value if refund.status else "POSTED",
            created_at=refund.created_at,
        )
        for refund in refunds
    ]
    return InvoiceRefundList(items=items)


@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> Response:
    invoice = db.query(Invoice).filter_by(id=invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    client_id = token.get("client_id")
    if not client_id or str(invoice.client_id) != str(client_id):
        raise HTTPException(status_code=403, detail="forbidden")

    if not invoice.pdf_object_key:
        raise HTTPException(status_code=404, detail="pdf not found")

    storage = S3Storage()
    pdf_bytes = storage.get_bytes(invoice.pdf_object_key)
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="pdf not found")

    AuditService(db).audit(
        event_type="INVOICE_DOWNLOADED",
        entity_type="invoice",
        entity_id=invoice.id,
        action="DOWNLOAD",
        after={"pdf_object_key": invoice.pdf_object_key},
        request_ctx=request_context_from_request(request, token=token),
    )

    return Response(content=pdf_bytes, media_type="application/pdf")


__all__ = ["router"]
