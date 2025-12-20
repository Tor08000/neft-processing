from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.models.operation import Operation, OperationStatus
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


BILLABLE_STATUSES: set[OperationStatus] = {
    OperationStatus.CAPTURED,
    OperationStatus.COMPLETED,
}


@dataclass
class BillingRunResult:
    billing_period: BillingPeriod
    period_from: date
    period_to: date
    clients_processed: int
    invoices_created: int
    invoices_rebuilt: int
    invoices_skipped: int
    invoice_lines_created: int
    total_amount: int


class BillingRunValidationError(ValueError):
    """Invalid parameters for billing run."""


class BillingPeriodClosedError(RuntimeError):
    """Requested billing period is not open for changes."""


class BillingRunService:
    """Manual, idempotent billing run against operations table."""

    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_billing_period(
        self,
        *,
        period_type: BillingPeriodType,
        start_at: datetime,
        end_at: datetime,
        tz: str,
    ) -> BillingPeriod:
        period = (
            self.db.query(BillingPeriod)
            .filter(BillingPeriod.period_type == period_type)
            .filter(BillingPeriod.start_at == start_at)
            .filter(BillingPeriod.end_at == end_at)
            .one_or_none()
        )
        if period:
            return period

        period = BillingPeriod(
            period_type=period_type,
            start_at=start_at,
            end_at=end_at,
            tz=tz,
            status=BillingPeriodStatus.OPEN,
        )
        self.db.add(period)
        self.db.flush()
        return period

    def _query_billable_operations(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        client_id: str | None = None,
    ) -> list[tuple[Operation, int]]:
        base_amount = case(
            (Operation.captured_amount > 0, Operation.captured_amount),
            (Operation.amount_settled > 0, Operation.amount_settled),
            else_=0,
        )
        billable_amount = func.greatest(base_amount - func.coalesce(Operation.refunded_amount, 0), 0)

        query = (
            self.db.query(Operation, billable_amount.label("billable_amount"))
            .filter(Operation.status.in_(BILLABLE_STATUSES))
            .filter(Operation.created_at >= start_at)
            .filter(Operation.created_at < end_at)
            .filter(billable_amount > 0)
        )
        if client_id:
            query = query.filter(Operation.client_id == client_id)

        results: list[tuple[Operation, int]] = []
        for operation, amount in query.all():
            results.append((operation, int(amount or 0)))
        return results

    def _build_lines(self, operations: Iterable[tuple[Operation, int]]) -> list[InvoiceLine]:
        lines: list[InvoiceLine] = []
        for operation, billable_amount in operations:
            product_id = operation.product_id or operation.product_code or "UNKNOWN"
            lines.append(
                InvoiceLine(
                    product_id=product_id,
                    liters=operation.quantity,
                    unit_price=operation.unit_price,
                    line_amount=billable_amount,
                    tax_amount=0,
                    operation_id=operation.operation_id,
                    card_id=operation.card_id,
                    partner_id=None,
                    azs_id=operation.merchant_id,
                )
            )
        return lines

    def _apply_invoice(
        self,
        *,
        billing_period: BillingPeriod,
        client_id: str,
        currency: str,
        period_from: date,
        period_to: date,
        lines: list[InvoiceLine],
    ) -> tuple[Invoice, str]:
        invoice = (
            self.db.query(Invoice)
            .filter(Invoice.client_id == client_id)
            .filter(Invoice.period_from == period_from)
            .filter(Invoice.period_to == period_to)
            .filter(Invoice.currency == currency)
            .filter(Invoice.billing_period_id == billing_period.id)
            .first()
        )

        if invoice and invoice.status != InvoiceStatus.DRAFT:
            return invoice, "skipped"

        if not invoice:
            invoice = Invoice(
                client_id=client_id,
                billing_period_id=billing_period.id,
                period_from=period_from,
                period_to=period_to,
                currency=currency,
                status=InvoiceStatus.DRAFT,
            )
            self.db.add(invoice)
            self.db.flush()
            action = "created"
        else:
            invoice.billing_period_id = billing_period.id
            self.db.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).delete(synchronize_session=False)
            action = "rebuilt"

        for line in lines:
            line.invoice_id = invoice.id

        invoice.lines = []
        invoice.lines.extend(lines)

        total_amount = sum(int(line.line_amount or 0) for line in lines)
        invoice.total_amount = total_amount
        invoice.tax_amount = sum(int(line.tax_amount or 0) for line in lines)
        invoice.total_with_tax = invoice.total_amount + invoice.tax_amount
        invoice.status = InvoiceStatus.DRAFT

        self.db.flush()
        return invoice, action

    def run(
        self,
        *,
        period_type: BillingPeriodType,
        start_at: datetime,
        end_at: datetime,
        tz: str,
        client_id: str | None = None,
    ) -> BillingRunResult:
        if end_at <= start_at:
            raise BillingRunValidationError("end_at must be greater than start_at")

        period_from = start_at.date()
        period_to = end_at.date()

        operations = self._query_billable_operations(start_at=start_at, end_at=end_at, client_id=client_id)
        logger.info(
            "billing.run.operations_found",
            extra={
                "count": len(operations),
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "client_filter": client_id,
            },
        )

        with self.db.begin():
            billing_period = self._get_or_create_billing_period(
                period_type=period_type,
                start_at=start_at,
                end_at=end_at,
                tz=tz,
            )
            if billing_period.status != BillingPeriodStatus.OPEN:
                raise BillingPeriodClosedError(f"Billing period {billing_period.id} is {billing_period.status}")

            grouped: dict[tuple[str, str], list[tuple[Operation, int]]] = {}
            for op, amount in operations:
                key = (op.client_id, op.currency or "RUB")
                grouped.setdefault(key, []).append((op, amount))

            invoices_created = 0
            invoices_rebuilt = 0
            invoices_skipped = 0
            invoice_lines_created = 0
            total_amount = 0
            processed_clients: set[str] = set()

            for (client_key, currency), items in grouped.items():
                processed_clients.add(client_key)
                lines = self._build_lines(items)
                invoice, action = self._apply_invoice(
                    billing_period=billing_period,
                    client_id=client_key,
                    currency=currency,
                    period_from=period_from,
                    period_to=period_to,
                    lines=lines,
                )

                if invoice.status != InvoiceStatus.DRAFT:
                    invoices_skipped += 1
                    continue

                if action == "created":
                    invoices_created += 1
                elif action == "rebuilt":
                    invoices_rebuilt += 1
                else:
                    invoices_skipped += 1

                invoice_lines_created += len(lines)
                total_amount += invoice.total_amount or 0

            result = BillingRunResult(
                billing_period=billing_period,
                period_from=period_from,
                period_to=period_to,
                clients_processed=len(processed_clients),
                invoices_created=invoices_created,
                invoices_rebuilt=invoices_rebuilt,
                invoices_skipped=invoices_skipped,
                invoice_lines_created=invoice_lines_created,
                total_amount=total_amount,
            )

        logger.info(
            "billing.run.completed",
            extra={
                "billing_period_id": billing_period.id,
                "clients_processed": result.clients_processed,
                "invoices_created": result.invoices_created,
                "invoices_rebuilt": result.invoices_rebuilt,
                "invoices_skipped": result.invoices_skipped,
                "invoice_lines_created": result.invoice_lines_created,
                "total_amount": result.total_amount,
            },
        )

        return result
