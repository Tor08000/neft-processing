from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceLine, InvoicePdfStatus, InvoiceStatus
from app.services.invoice_state_machine import InvoiceStateMachine, InvoiceTransitionContext


@dataclass
class BillingLineData:
    """Normalized payload for a single invoice line."""

    product_id: str
    liters: object | None
    unit_price: object | None
    line_amount: int
    tax_amount: int = 0
    operation_id: str | None = None
    card_id: str | None = None
    partner_id: str | None = None
    azs_id: str | None = None


@dataclass
class BillingInvoiceData:
    """Result of billing calculation for a client and period."""

    client_id: str
    period_from: date
    period_to: date
    currency: str
    lines: Iterable[BillingLineData]
    status: InvoiceStatus = InvoiceStatus.DRAFT
    external_number: str | None = None
    issued_at: datetime | None = None
    sent_at: datetime | None = None
    paid_at: datetime | None = None
    pdf_url: str | None = None
    pdf_status: InvoicePdfStatus = InvoicePdfStatus.NONE
    pdf_generated_at: datetime | None = None
    pdf_hash: str | None = None
    pdf_version: int = 1
    pdf_error: str | None = None


class BillingRepository:
    """Persistence layer for invoices and their lines."""

    def __init__(self, db: Session):
        self.db = db
        self.state_machine = InvoiceStateMachine()

    def create_invoice(self, data: BillingInvoiceData, *, auto_commit: bool = True) -> Invoice:
        """Create invoice with lines, computing totals from provided items."""

        lines = list(data.lines)

        total_amount = sum(int(line.line_amount or 0) for line in lines)
        tax_amount = sum(int(line.tax_amount or 0) for line in lines)
        total_with_tax = total_amount + tax_amount
        amount_paid = 0
        amount_due = total_with_tax - amount_paid

        invoice = Invoice(
            client_id=data.client_id,
            period_from=data.period_from,
            period_to=data.period_to,
            currency=data.currency,
            total_amount=total_amount,
            tax_amount=tax_amount,
            total_with_tax=total_with_tax,
            amount_paid=amount_paid,
            amount_due=amount_due,
            status=data.status,
            external_number=data.external_number,
            issued_at=data.issued_at,
            sent_at=data.sent_at,
            paid_at=data.paid_at,
            pdf_url=data.pdf_url,
            pdf_status=data.pdf_status,
            pdf_generated_at=data.pdf_generated_at,
            pdf_hash=data.pdf_hash,
            pdf_version=data.pdf_version if data.pdf_version is not None else 1,
            pdf_error=data.pdf_error,
        )
        self.db.add(invoice)
        self.db.flush()

        invoice.lines = [
            InvoiceLine(
                invoice_id=invoice.id,
                product_id=line.product_id,
                liters=line.liters,
                unit_price=line.unit_price,
                line_amount=line.line_amount,
                tax_amount=line.tax_amount,
                operation_id=line.operation_id or f"manual-{uuid4()}",
                card_id=line.card_id,
                partner_id=line.partner_id,
                azs_id=line.azs_id,
            )
            for line in lines
        ]

        context = InvoiceTransitionContext(
            actor="billing_repository",
            reason="create_invoice",
            payments_total=invoice.amount_paid,
        )
        self.state_machine.apply_transition(invoice, invoice.status, context=context)

        if auto_commit:
            self.db.commit()
            self.db.refresh(invoice)
        else:
            self.db.flush()
        return invoice

    def find_invoices(
        self,
        *,
        client_id: str | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
        status: InvoiceStatus | None = None,
        exclude_cancelled: bool = False,
    ) -> list[Invoice]:
        """Search invoices by client, period and status."""

        query = self.db.query(Invoice)
        if client_id:
            query = query.filter(Invoice.client_id == client_id)
        if period_from:
            query = query.filter(Invoice.period_from >= period_from)
        if period_to:
            query = query.filter(Invoice.period_to <= period_to)
        if status:
            query = query.filter(Invoice.status == status)
        if exclude_cancelled:
            query = query.filter(Invoice.status != InvoiceStatus.CANCELLED)
        return query.order_by(Invoice.created_at.desc()).all()

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        """Retrieve invoice by identifier."""

        return self.db.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()

    def update_status(
        self,
        invoice_id: str,
        status: InvoiceStatus,
        *,
        issued_at: datetime | None = None,
        paid_at: datetime | None = None,
        actor: str | None = "billing_repository",
        reason: str | None = "status_update",
        allow_cancel_paid: bool = False,
    ) -> Invoice | None:
        """Update invoice status and adjust lifecycle timestamps."""

        query = self.db.query(Invoice).filter(Invoice.id == invoice_id)
        if getattr(getattr(self.db.bind, "dialect", None), "name", None) == "postgresql":
            query = query.with_for_update()
        invoice = query.one_or_none()
        if invoice is None:
            return None

        payments_total = invoice.amount_paid
        if status == InvoiceStatus.PAID:
            payments_total = invoice.total_with_tax or invoice.total_amount or payments_total

        context = InvoiceTransitionContext(
            actor=actor,
            reason=reason,
            source="billing_repository",
            allow_cancel_paid=allow_cancel_paid,
            payments_total=payments_total,
        )
        now_hint = paid_at if status == InvoiceStatus.PAID and paid_at else issued_at
        self.state_machine.apply_transition(invoice, status, now=now_hint, context=context)

        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice
