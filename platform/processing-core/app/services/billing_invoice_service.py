from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.clearing_batch import ClearingBatch
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus
from app.models.operation import Operation, OperationStatus
from app.services.billing_metrics import metrics as billing_metrics
from app.services.invoice_pdf import InvoicePdfService
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


def close_clearing_period(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    tenant_id: int,
) -> ClearingBatch:
    # Use date_from/date_to consistently with the unique constraint on
    # (tenant_id, date_from, date_to); do not introduce parallel period_from/period_to fields.
    if date_from > date_to:
        raise ValueError("invalid_period")

    billing_metrics.start_run(date_from.isoformat(), date_to.isoformat())

    existing = (
        db.query(ClearingBatch)
        .filter(ClearingBatch.tenant_id == tenant_id)
        .filter(ClearingBatch.date_from == date_from)
        .filter(ClearingBatch.date_to == date_to)
        .one_or_none()
    )
    if existing:
        return existing

    base_query = (
        db.query(Operation)
        .filter(Operation.status == OperationStatus.CAPTURED)
        .filter(func.date(Operation.created_at) >= date_from)
        .filter(func.date(Operation.created_at) <= date_to)
    )

    amount_expr = func.coalesce(Operation.amount_settled, Operation.amount)
    total_amount, total_qty, txn_count = (
        db.query(
            func.coalesce(func.sum(amount_expr), 0),
            func.coalesce(func.sum(Operation.quantity), 0),
            func.count(Operation.id),
        )
        .filter(Operation.status == OperationStatus.CAPTURED)
        .filter(func.date(Operation.created_at) >= date_from)
        .filter(func.date(Operation.created_at) <= date_to)
        .one()
    )

    merchant_id = base_query.with_entities(Operation.merchant_id).limit(1).scalar()
    if not merchant_id:
        merchant_id = f"tenant-{tenant_id}"

    batch = ClearingBatch(
        merchant_id=merchant_id,
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
        total_amount=int(total_amount or 0),
        total_qty=Decimal(total_qty or 0),
        operations_count=int(txn_count or 0),
        status="CONFIRMED",
        state="CLOSED",
        closed_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = (
        db.query(ClearingBatch)
        .filter(ClearingBatch.tenant_id == tenant_id)
        .filter(ClearingBatch.date_from == date_from)
        .filter(ClearingBatch.date_to == date_to)
        .one_or_none()
    )
        if existing:
            return existing
        raise
    db.commit()
    return batch


def _invoice_number_for(invoice_id: str, *, period_to: date) -> str:
    period_key = period_to.strftime("%Y%m%d")
    short_id = invoice_id.replace("-", "")[:8]
    return f"INV-{period_key}-{short_id}"


def _resolve_invoice_client_id(db: Session, batch: ClearingBatch) -> str:
    client_id = (
        db.query(Operation.client_id)
        .filter(Operation.status == OperationStatus.CAPTURED)
        .filter(func.date(Operation.created_at) >= batch.date_from)
        .filter(func.date(Operation.created_at) <= batch.date_to)
        .limit(1)
        .scalar()
    )
    if client_id:
        return client_id
    if batch.tenant_id is not None:
        return f"tenant-{batch.tenant_id}"
    return "unknown"


def _resolve_invoice_currency(db: Session, batch: ClearingBatch) -> str:
    currency = (
        db.query(Operation.currency)
        .filter(Operation.status == OperationStatus.CAPTURED)
        .filter(func.date(Operation.created_at) >= batch.date_from)
        .filter(func.date(Operation.created_at) <= batch.date_to)
        .limit(1)
        .scalar()
    )
    return currency or "RUB"


def generate_invoice_for_batch(
    db: Session,
    *,
    batch_id: str,
    run_pdf_sync: bool,
) -> Invoice:
    batch = db.query(ClearingBatch).filter(ClearingBatch.id == batch_id).one_or_none()
    if not batch:
        raise ValueError("batch_not_found")

    existing = db.query(Invoice).filter(Invoice.clearing_batch_id == batch_id).one_or_none()
    if existing:
        if not existing.pdf_object_key:
            existing.pdf_object_key = f"invoices/{existing.id}.pdf"
            db.add(existing)
        if run_pdf_sync and not existing.pdf_url:
            _generate_invoice_pdf_sync(db, existing)
        db.commit()
        return existing

    try:
        total_amount = int(batch.total_amount or 0)
        initial_status = InvoiceStatus.SENT if run_pdf_sync else InvoiceStatus.ISSUED
        issued_at = datetime.now(timezone.utc)
        invoice = Invoice(
            clearing_batch_id=batch.id,
            client_id=_resolve_invoice_client_id(db, batch),
            number="",
            external_number=None,
            period_from=batch.date_from,
            period_to=batch.date_to,
            currency=_resolve_invoice_currency(db, batch),
            total_amount=total_amount,
            tax_amount=0,
            total_with_tax=total_amount,
            amount_paid=0,
            amount_due=total_amount,
            status=initial_status,
            issued_at=issued_at,
            sent_at=issued_at if initial_status == InvoiceStatus.SENT else None,
            pdf_status=InvoicePdfStatus.QUEUED if not run_pdf_sync else InvoicePdfStatus.NONE,
            pdf_object_key=None,
        )
        db.add(invoice)
        db.flush()
        number = _invoice_number_for(invoice.id, period_to=batch.date_to)
        invoice.number = number
        invoice.external_number = number
        invoice.pdf_object_key = f"invoices/{invoice.id}.pdf"
        billing_metrics.mark_generated()
    except IntegrityError:
        db.rollback()
        existing = db.query(Invoice).filter(Invoice.clearing_batch_id == batch_id).one_or_none()
        if existing:
            return existing
        raise
    except Exception:  # noqa: BLE001
        billing_metrics.mark_error()
        raise

    if run_pdf_sync:
        _generate_invoice_pdf_sync(db, invoice)
        db.commit()
        db.refresh(invoice)
    else:
        db.commit()
        from app.tasks.billing_pdf import generate_invoice_pdf

        try:
            generate_invoice_pdf.delay(invoice.id)
        except Exception:  # noqa: BLE001
            logger.warning("invoice.pdf.enqueue_failed", extra={"invoice_id": invoice.id})
    return invoice


def _generate_invoice_pdf_sync(db: Session, invoice: Invoice) -> None:
    pdf_service = InvoicePdfService(db)
    pdf_service.generate(invoice, force=False)


__all__ = ["close_clearing_period", "generate_invoice_for_batch"]
