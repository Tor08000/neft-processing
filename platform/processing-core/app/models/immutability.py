from __future__ import annotations

from sqlalchemy import event, inspect
from sqlalchemy.orm import object_session

from app.models.billing_period import BillingPeriod, BillingPeriodStatus
from app.models.client_actions import DocumentAcknowledgement
from app.models.documents import Document, DocumentFile, DocumentStatus
from app.models.invoice import Invoice, InvoiceLine


class ImmutableRecordError(ValueError):
    """Raised when a finalized/acknowledged record is mutated."""


def _load_billing_period_status(invoice: Invoice) -> BillingPeriodStatus | None:
    session = object_session(invoice)
    if session is None or not invoice.billing_period_id:
        return None
    period = (
        session.query(BillingPeriod)
        .filter(BillingPeriod.id == invoice.billing_period_id)
        .one_or_none()
    )
    return period.status if period else None


def _is_invoice_charge_locked(invoice: Invoice) -> bool:
    return _load_billing_period_status(invoice) in {BillingPeriodStatus.FINALIZED, BillingPeriodStatus.LOCKED}


@event.listens_for(DocumentFile, "before_update")
@event.listens_for(DocumentFile, "before_delete")
def _block_document_file_mutation(mapper, connection, target: DocumentFile) -> None:
    session = object_session(target)
    if session is None:
        return
    document = session.query(Document).filter(Document.id == target.document_id).one_or_none()
    if document and document.status in {DocumentStatus.ACKNOWLEDGED, DocumentStatus.FINALIZED}:
        raise ImmutableRecordError("document_file_immutable")


@event.listens_for(DocumentAcknowledgement, "before_update")
@event.listens_for(DocumentAcknowledgement, "before_delete")
def _block_document_ack_mutation(mapper, connection, target: DocumentAcknowledgement) -> None:
    raise ImmutableRecordError("document_acknowledgement_immutable")


@event.listens_for(Document, "before_update")
def _block_document_hash_mutation(mapper, connection, target: Document) -> None:
    if target.status not in {DocumentStatus.ACKNOWLEDGED, DocumentStatus.FINALIZED}:
        return
    state = inspect(target)
    if state.attrs.document_hash.history.has_changes():
        raise ImmutableRecordError("document_hash_immutable")


@event.listens_for(InvoiceLine, "before_insert")
@event.listens_for(InvoiceLine, "before_update")
@event.listens_for(InvoiceLine, "before_delete")
def _block_invoice_line_mutation(mapper, connection, target: InvoiceLine) -> None:
    session = object_session(target)
    if session is None:
        return
    invoice = session.query(Invoice).filter(Invoice.id == target.invoice_id).one_or_none()
    if invoice and _is_invoice_charge_locked(invoice):
        raise ImmutableRecordError("invoice_line_immutable")


@event.listens_for(Invoice, "before_update")
def _block_invoice_charge_mutation(mapper, connection, target: Invoice) -> None:
    if not _is_invoice_charge_locked(target):
        return
    state = inspect(target)
    protected_fields = {"total_amount", "tax_amount", "total_with_tax", "period_from", "period_to", "currency"}
    if target.billing_period_id and state.attrs.billing_period_id.history.has_changes():
        raise ImmutableRecordError("invoice_charge_immutable")
    for field in protected_fields:
        if state.attrs[field].history.has_changes():
            raise ImmutableRecordError("invoice_charge_immutable")


__all__ = ["ImmutableRecordError"]
