from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.audit_log import AuditVisibility
from app.schemas.billing_payment_intakes import (
    BillingPaymentIntakeStatus,
    PaymentIntakeApproveRequest,
    PaymentIntakeListResponse,
    PaymentIntakeOut,
    PaymentIntakeRejectRequest,
)
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.billing_payment_intakes import (
    get_invoice,
    get_payment_intake,
    list_payment_intakes,
    review_payment_intake,
)
from app.services.client_notifications import ClientNotificationSeverity, create_notification, resolve_client_email
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.payment_intake_attachment_storage import PaymentIntakeAttachmentStorage
from app.services.subscription_billing import update_invoice_status


router = APIRouter(prefix="/billing/payment-intakes", tags=["admin-billing"])


def _serialize_payment_intake(row: dict, *, proof_url: str | None = None) -> PaymentIntakeOut:
    proof = None
    if row.get("proof_object_key"):
        proof = {
            "object_key": row.get("proof_object_key"),
            "file_name": row.get("proof_file_name"),
            "content_type": row.get("proof_content_type"),
            "size": row.get("proof_size"),
        }
    return PaymentIntakeOut(
        id=row["id"],
        org_id=row["org_id"],
        invoice_id=row["invoice_id"],
        status=row["status"],
        amount=row["amount"],
        currency=row["currency"],
        payer_name=row.get("payer_name"),
        payer_inn=row.get("payer_inn"),
        bank_reference=row.get("bank_reference"),
        paid_at_claimed=row.get("paid_at_claimed"),
        comment=row.get("comment"),
        proof=proof,
        proof_url=proof_url,
        created_by_user_id=row.get("created_by_user_id"),
        reviewed_by_admin=row.get("reviewed_by_admin"),
        reviewed_at=row.get("reviewed_at"),
        review_note=row.get("review_note"),
        created_at=row.get("created_at"),
    )


def _reviewed_by(token: dict) -> str:
    return str(token.get("user_id") or token.get("sub") or token.get("email") or "admin")


@router.get("", response_model=PaymentIntakeListResponse)
def admin_list_payment_intakes(
    status: BillingPaymentIntakeStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> PaymentIntakeListResponse:
    rows, total = list_payment_intakes(db, status=status.value if status else None, limit=limit, offset=offset)
    storage = PaymentIntakeAttachmentStorage()
    items = []
    for row in rows:
        proof_url = None
        if row.get("proof_object_key"):
            proof_url = storage.presign_download(object_key=row["proof_object_key"], expires=3600)
        items.append(_serialize_payment_intake(row, proof_url=proof_url))
    return PaymentIntakeListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/{intake_id}/approve", response_model=PaymentIntakeOut)
def approve_payment_intake(
    intake_id: int,
    payload: PaymentIntakeApproveRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> PaymentIntakeOut:
    intake = get_payment_intake(db, intake_id=intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail="payment_intake_not_found")
    if intake["status"] == BillingPaymentIntakeStatus.APPROVED.value:
        raise HTTPException(status_code=409, detail="already_approved")

    reviewed_by = _reviewed_by(token)
    updated = review_payment_intake(
        db,
        intake_id=intake_id,
        status=BillingPaymentIntakeStatus.APPROVED.value,
        reviewed_by_admin=reviewed_by,
        review_note=payload.review_note,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="payment_intake_not_found")

    invoice = get_invoice(db, invoice_id=intake["invoice_id"])
    if not invoice:
        raise HTTPException(status_code=404, detail="invoice_not_found")

    update_invoice_status(
        db,
        invoice_id=intake["invoice_id"],
        status="PAID",
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    get_org_entitlements_snapshot(db, org_id=invoice["org_id"])

    AuditService(db).audit(
        event_type="INVOICE_MARKED_PAID",
        entity_type="billing_invoice",
        entity_id=str(intake["invoice_id"]),
        action="PAID",
        visibility=AuditVisibility.INTERNAL,
        after={"status": "PAID"},
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    if invoice.get("subscription_id"):
        AuditService(db).audit(
            event_type="SUBSCRIPTION_STATUS_CHANGED",
            entity_type="org_subscription",
            entity_id=str(invoice["subscription_id"]),
            action="ACTIVATE",
            visibility=AuditVisibility.INTERNAL,
            after={"status": "ACTIVE"},
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )

    AuditService(db).audit(
        event_type="PAYMENT_INTAKE_APPROVED",
        entity_type="billing_payment_intake",
        entity_id=str(intake_id),
        action="APPROVE",
        visibility=AuditVisibility.INTERNAL,
        after={
            "org_id": intake["org_id"],
            "invoice_id": intake["invoice_id"],
            "amount": str(intake["amount"]),
            "currency": intake["currency"],
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    client_email = resolve_client_email(db, str(intake["org_id"]))
    create_notification(
        db,
        org_id=str(intake["org_id"]),
        event_type="payment_intake_approved",
        severity=ClientNotificationSeverity.INFO,
        title="Оплата подтверждена",
        body=f"Оплата по счету №{intake['invoice_id']} подтверждена.",
        link=f"/finance/invoices/{intake['invoice_id']}",
        entity_type="billing_payment_intake",
        entity_id=str(intake_id),
        email_to=client_email,
        email_context={"invoice_id": str(intake["invoice_id"])},
    )
    db.commit()

    return _serialize_payment_intake(updated)


@router.post("/{intake_id}/reject", response_model=PaymentIntakeOut)
def reject_payment_intake(
    intake_id: int,
    payload: PaymentIntakeRejectRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> PaymentIntakeOut:
    intake = get_payment_intake(db, intake_id=intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail="payment_intake_not_found")

    reviewed_by = _reviewed_by(token)
    updated = review_payment_intake(
        db,
        intake_id=intake_id,
        status=BillingPaymentIntakeStatus.REJECTED.value,
        reviewed_by_admin=reviewed_by,
        review_note=payload.review_note,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="payment_intake_not_found")

    AuditService(db).audit(
        event_type="PAYMENT_INTAKE_REJECTED",
        entity_type="billing_payment_intake",
        entity_id=str(intake_id),
        action="REJECT",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.review_note,
        after={
            "org_id": intake["org_id"],
            "invoice_id": intake["invoice_id"],
            "amount": str(intake["amount"]),
            "currency": intake["currency"],
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    client_email = resolve_client_email(db, str(intake["org_id"]))
    create_notification(
        db,
        org_id=str(intake["org_id"]),
        event_type="payment_intake_rejected",
        severity=ClientNotificationSeverity.WARNING,
        title="Оплата отклонена",
        body=f"Оплата по счету №{intake['invoice_id']} отклонена.",
        link=f"/finance/invoices/{intake['invoice_id']}",
        entity_type="billing_payment_intake",
        entity_id=str(intake_id),
        email_to=client_email,
        email_context={"invoice_id": str(intake["invoice_id"])},
    )
    db.commit()

    return _serialize_payment_intake(updated)
