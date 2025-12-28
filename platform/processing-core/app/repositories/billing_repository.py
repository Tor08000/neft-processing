from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod, BillingPeriodStatus
from app.models.invoice import Invoice, InvoiceLine, InvoicePdfStatus, InvoiceStatus
from app.services.internal_ledger import InternalLedgerService
from app.services.billing_periods import BillingPeriodConflict
from app.services.invoice_state_machine import InvoiceStateMachine


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
    billing_period_id: str | None = None
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

    def create_invoice(self, data: BillingInvoiceData, *, auto_commit: bool = True) -> Invoice:
        """Create invoice with lines, computing totals from provided items."""

        lines = list(data.lines)

        total_amount = sum(int(line.line_amount or 0) for line in lines)
        tax_amount = sum(int(line.tax_amount or 0) for line in lines)
        total_with_tax = total_amount + tax_amount
        amount_paid = 0
        amount_due = total_with_tax - amount_paid

        if data.billing_period_id:
            period = (
                self.db.query(BillingPeriod)
                .filter(BillingPeriod.id == data.billing_period_id)
                .one_or_none()
            )
            if not period:
                raise ValueError("billing period not found")
            if period.status != BillingPeriodStatus.OPEN:
                raise BillingPeriodConflict(f"Billing period {period.id} is {period.status.value}")

        invoice = Invoice(
            client_id=data.client_id,
            period_from=data.period_from,
            period_to=data.period_to,
            currency=data.currency,
            billing_period_id=data.billing_period_id,
            status=InvoiceStatus.DRAFT,
            total_amount=total_amount,
            tax_amount=tax_amount,
            total_with_tax=total_with_tax,
            amount_paid=amount_paid,
            amount_due=amount_due,
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

        state_machine = InvoiceStateMachine(invoice, db=self.db)
        state_machine.transition(
            to=data.status,
            actor="billing_repository",
            reason="create_invoice",
        )
        InternalLedgerService(self.db).post_invoice_issued(invoice=invoice, tenant_id=0)

        if auto_commit:
            self.db.commit()
            self.db.refresh(invoice)
        else:
            self.db.flush()
        return invoice

    def _build_invoice_query(
        self,
        *,
        client_id: str | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
        status: InvoiceStatus | list[InvoiceStatus] | tuple[InvoiceStatus, ...] | None = None,
        issued_from: datetime | None = None,
        issued_to: datetime | None = None,
        exclude_cancelled: bool = False,
    ):
        query = self.db.query(Invoice)
        if client_id:
            query = query.filter(Invoice.client_id == client_id)
        if period_from:
            query = query.filter(Invoice.period_from >= period_from)
        if period_to:
            query = query.filter(Invoice.period_to <= period_to)
        if issued_from:
            query = query.filter(func.coalesce(Invoice.issued_at, Invoice.created_at) >= issued_from)
        if issued_to:
            query = query.filter(func.coalesce(Invoice.issued_at, Invoice.created_at) <= issued_to)
        if status:
            if isinstance(status, (list, tuple)):
                query = query.filter(Invoice.status.in_(status))
            else:
                query = query.filter(Invoice.status == status)
        if exclude_cancelled:
            query = query.filter(Invoice.status != InvoiceStatus.CANCELLED)
        return query

    def find_invoices(
        self,
        *,
        client_id: str | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
        status: InvoiceStatus | list[InvoiceStatus] | tuple[InvoiceStatus, ...] | None = None,
        exclude_cancelled: bool = False,
    ) -> list[Invoice]:
        """Search invoices by client, period and status."""

        query = self._build_invoice_query(
            client_id=client_id,
            period_from=period_from,
            period_to=period_to,
            status=status,
            exclude_cancelled=exclude_cancelled,
        )
        return query.order_by(Invoice.created_at.desc()).all()

    def list_invoices(
        self,
        *,
        client_id: str | None = None,
        issued_from: datetime | None = None,
        issued_to: datetime | None = None,
        status: list[InvoiceStatus] | None = None,
        exclude_cancelled: bool = False,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> tuple[list[Invoice], int]:
        query = self._build_invoice_query(
            client_id=client_id,
            issued_from=issued_from,
            issued_to=issued_to,
            status=status,
            exclude_cancelled=exclude_cancelled,
        )
        total = query.count()
        ordering = Invoice.issued_at.desc().nullslast() if sort_desc else Invoice.issued_at.asc().nullsfirst()
        query = query.order_by(ordering, Invoice.created_at.desc())
        items = query.offset(offset).limit(limit).all()
        return items, total

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
    ) -> Invoice | None:
        """Update invoice status and adjust lifecycle timestamps."""

        query = self.db.query(Invoice).filter(Invoice.id == invoice_id)
        if getattr(getattr(self.db.bind, "dialect", None), "name", None) == "postgresql":
            query = query.with_for_update()
        invoice = query.one_or_none()
        if invoice is None:
            return None

        state_machine = InvoiceStateMachine(invoice, db=self.db, now_provider=lambda: paid_at or issued_at or datetime.utcnow())
        state_machine.transition(
            to=status,
            actor=actor or "billing_repository",
            reason=reason or "status_update",
        )
        if status == InvoiceStatus.ISSUED:
            InternalLedgerService(self.db).post_invoice_issued(invoice=invoice, tenant_id=0)

        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice
