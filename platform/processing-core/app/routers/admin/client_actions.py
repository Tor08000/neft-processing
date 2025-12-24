from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.client_actions import (
    InvoiceMessage,
    InvoiceMessageSenderType,
    InvoiceThread,
    InvoiceThreadStatus,
    ReconciliationRequest,
    ReconciliationRequestStatus,
)
from app.models.audit_log import AuditVisibility
from app.models.invoice import Invoice
from app.schemas.client_actions import (
    AdminInvoiceMessageRequest,
    InvoiceMessageCreateResponse,
    InvoiceThreadCloseResponse,
    ReconciliationAttachResultRequest,
    ReconciliationRequestOut,
)
from app.services.audit_service import AuditService, request_context_from_request

router = APIRouter()


def _update_reconciliation_status(
    request_item: ReconciliationRequest,
    status: ReconciliationRequestStatus,
    *,
    db: Session,
    request: Request,
    token: dict | None,
    event_type: str,
    visibility: AuditVisibility,
    note: dict | None = None,
) -> None:
    before_status = request_item.status
    request_item.status = status
    db.commit()

    AuditService(db).audit(
        event_type=event_type,
        entity_type="reconciliation_request",
        entity_id=str(request_item.id),
        action="UPDATE",
        visibility=visibility,
        before={"status": before_status.value if before_status else None},
        after={"status": request_item.status.value, **(note or {})},
        request_ctx=request_context_from_request(request, token=token),
    )


def _get_reconciliation_request(db: Session, request_id: str) -> ReconciliationRequest:
    request_item = db.query(ReconciliationRequest).filter(ReconciliationRequest.id == request_id).one_or_none()
    if request_item is None:
        raise HTTPException(status_code=404, detail="reconciliation_request_not_found")
    return request_item


@router.post("/reconciliation-requests/{request_id}/mark-in-progress", response_model=ReconciliationRequestOut)
def mark_reconciliation_in_progress(
    request_id: str,
    token: dict = Depends(require_admin_user),
    request: Request,
    db: Session = Depends(get_db),
) -> ReconciliationRequestOut:
    request_item = _get_reconciliation_request(db, request_id)
    _update_reconciliation_status(
        request_item,
        ReconciliationRequestStatus.IN_PROGRESS,
        db=db,
        request=request,
        token=token,
        event_type="RECONCILIATION_REQUEST_STATUS_CHANGED",
        visibility=AuditVisibility.INTERNAL,
    )
    db.refresh(request_item)
    return ReconciliationRequestOut.model_validate(request_item)


@router.post("/reconciliation-requests/{request_id}/attach-result", response_model=ReconciliationRequestOut)
def attach_reconciliation_result(
    request_id: str,
    payload: ReconciliationAttachResultRequest,
    token: dict = Depends(require_admin_user),
    request: Request,
    db: Session = Depends(get_db),
) -> ReconciliationRequestOut:
    request_item = _get_reconciliation_request(db, request_id)
    before_status = request_item.status
    request_item.result_object_key = payload.object_key
    request_item.result_bucket = payload.bucket
    request_item.result_hash_sha256 = payload.result_hash_sha256
    request_item.status = ReconciliationRequestStatus.GENERATED
    request_item.generated_at = datetime.now(timezone.utc)
    db.commit()

    AuditService(db).audit(
        event_type="RECONCILIATION_GENERATED",
        entity_type="reconciliation_request",
        entity_id=str(request_item.id),
        action="UPDATE",
        visibility=AuditVisibility.PUBLIC,
        before={"status": before_status.value if before_status else None},
        after={
            "status": request_item.status.value,
            "result_object_key": payload.object_key,
            "result_hash_sha256": payload.result_hash_sha256,
        },
        request_ctx=request_context_from_request(request, token=token),
    )

    db.refresh(request_item)
    return ReconciliationRequestOut.model_validate(request_item)


@router.post("/reconciliation-requests/{request_id}/mark-sent", response_model=ReconciliationRequestOut)
def mark_reconciliation_sent(
    request_id: str,
    token: dict = Depends(require_admin_user),
    request: Request,
    db: Session = Depends(get_db),
) -> ReconciliationRequestOut:
    request_item = _get_reconciliation_request(db, request_id)
    request_item.sent_at = datetime.now(timezone.utc)
    _update_reconciliation_status(
        request_item,
        ReconciliationRequestStatus.SENT,
        db=db,
        request=request,
        token=token,
        event_type="RECONCILIATION_SENT",
        visibility=AuditVisibility.PUBLIC,
    )
    db.refresh(request_item)
    return ReconciliationRequestOut.model_validate(request_item)


@router.post("/invoices/{invoice_id}/messages", response_model=InvoiceMessageCreateResponse, status_code=201)
def admin_create_invoice_message(
    invoice_id: str,
    payload: AdminInvoiceMessageRequest,
    token: dict = Depends(require_admin_user),
    request: Request,
    db: Session = Depends(get_db),
) -> InvoiceMessageCreateResponse:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")

    thread = db.query(InvoiceThread).filter(InvoiceThread.invoice_id == invoice_id).one_or_none()
    if thread is None:
        thread = InvoiceThread(
            invoice_id=invoice_id,
            client_id=str(invoice.client_id),
            status=InvoiceThreadStatus.WAITING_CLIENT,
        )
        db.add(thread)
        db.flush()
    elif thread.status == InvoiceThreadStatus.CLOSED:
        thread.status = InvoiceThreadStatus.WAITING_CLIENT
        thread.closed_at = None
    else:
        thread.status = InvoiceThreadStatus.WAITING_CLIENT

    message = InvoiceMessage(
        thread_id=thread.id,
        sender_type=InvoiceMessageSenderType.SUPPORT,
        sender_user_id=token.get("user_id") or token.get("sub"),
        sender_email=token.get("email"),
        message=payload.message,
    )
    thread.last_message_at = datetime.now(timezone.utc)
    db.add(message)
    db.commit()
    db.refresh(message)

    AuditService(db).audit(
        event_type="INVOICE_MESSAGE_CREATED",
        entity_type="invoice",
        entity_id=invoice_id,
        action="CREATE",
        visibility=AuditVisibility.PUBLIC,
        after={
            "thread_id": str(thread.id),
            "message_id": str(message.id),
            "sender_type": message.sender_type.value,
        },
        request_ctx=request_context_from_request(request, token=token),
    )

    return InvoiceMessageCreateResponse(
        thread_id=str(thread.id),
        message_id=str(message.id),
        status=thread.status.value,
    )


@router.post("/invoice-threads/{thread_id}/close", response_model=InvoiceThreadCloseResponse)
def close_invoice_thread(
    thread_id: str,
    token: dict = Depends(require_admin_user),
    request: Request,
    db: Session = Depends(get_db),
) -> InvoiceThreadCloseResponse:
    thread = db.query(InvoiceThread).filter(InvoiceThread.id == thread_id).one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="invoice_thread_not_found")

    thread.status = InvoiceThreadStatus.CLOSED
    thread.closed_at = datetime.now(timezone.utc)
    db.commit()

    AuditService(db).audit(
        event_type="INVOICE_THREAD_CLOSED",
        entity_type="invoice_thread",
        entity_id=str(thread.id),
        action="UPDATE",
        visibility=AuditVisibility.INTERNAL,
        after={"status": thread.status.value, "closed_at": thread.closed_at},
        request_ctx=request_context_from_request(request, token=token),
    )

    return InvoiceThreadCloseResponse(thread_id=str(thread.id), status=thread.status.value, closed_at=thread.closed_at)
