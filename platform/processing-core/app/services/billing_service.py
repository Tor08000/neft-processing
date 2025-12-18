from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.models.client import Client
from app.models.operation import OperationType, ProductType
from app.models.invoice import Invoice, InvoiceStatus
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository
from app.models.billing_summary import BillingSummary
from app.models.operation import Operation, OperationStatus
from app.services.pricing_service import PriceQuote, get_effective_price
from app.services.billing_metrics import metrics as billing_metrics
from neft_shared.logging_setup import get_logger


logger = get_logger(__name__)


@dataclass
class OperationCharge:
    """Calculated billing line for a single operation."""

    operation_id: str
    tariff_id: str
    product_id: str | None
    partner_id: str | None
    azs_id: str | None
    currency: str
    quantity: Decimal
    client_price_per_liter: Decimal
    cost_price_per_liter: Decimal | None
    charge_amount: Decimal
    cost_amount: Decimal | None
    margin_amount: Decimal | None
    tariff_price_id: int


@dataclass
class BillingTotals:
    """Aggregated billing totals per currency."""

    charge_amount: Decimal
    cost_amount: Decimal | None
    margin_amount: Decimal | None


@dataclass
class BillingCalculationResult:
    """Result of billing calculation for a client within a period."""

    client_id: str
    totals_by_currency: Dict[str, BillingTotals]
    items: List[OperationCharge]


def _decimalize(value: Decimal | float | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


BILLABLE_STATUSES = {
    OperationStatus.POSTED,
    OperationStatus.COMPLETED,
    OperationStatus.REFUNDED,
    OperationStatus.REVERSED,
}


def calculate_client_charges(
    db: Session,
    *,
    client_id: str,
    date_from: datetime,
    date_to: datetime,
) -> BillingCalculationResult:
    """Calculate billing amounts for client operations within the period."""

    operations = (
        db.query(Operation)
        .filter(Operation.client_id == client_id)
        .filter(Operation.created_at >= date_from)
        .filter(Operation.created_at <= date_to)
        .filter(Operation.status.in_(BILLABLE_STATUSES))
        .all()
    )

    items: list[OperationCharge] = []
    totals: dict[str, dict[str, Decimal | bool]] = {}

    for operation in operations:
        if not operation.tariff_id:
            raise ValueError(f"Tariff is not set for operation {operation.id}")

        product_id = operation.product_id or (
            operation.product_type.value if operation.product_type else None
        )
        if not product_id:
            raise ValueError(f"Product is not set for operation {operation.id}")
        if operation.quantity is None:
            raise ValueError(f"Quantity is not set for operation {operation.id}")

        quantity = _decimalize(operation.quantity)
        sign = (
            Decimal("-1")
            if operation.status in {OperationStatus.REFUNDED, OperationStatus.REVERSED}
            or operation.operation_type in {OperationType.REFUND, OperationType.REVERSE}
            else Decimal("1")
        )

        price_quote: PriceQuote = get_effective_price(
            db,
            tariff_id=operation.tariff_id,
            product_id=product_id,
            partner_id=operation.merchant_id,
            azs_id=operation.terminal_id,
            occurred_at=operation.created_at,
        )

        charge_amount = price_quote.client_price_per_liter * quantity * sign
        cost_amount = (
            price_quote.cost_price_per_liter * quantity * sign
            if price_quote.cost_price_per_liter is not None
            else None
        )
        margin_amount = charge_amount - cost_amount if cost_amount is not None else None

        items.append(
            OperationCharge(
                operation_id=str(operation.id),
                tariff_id=operation.tariff_id,
                product_id=product_id,
                partner_id=operation.merchant_id,
                azs_id=operation.terminal_id,
                currency=price_quote.currency,
                quantity=quantity * sign,
                client_price_per_liter=price_quote.client_price_per_liter,
                cost_price_per_liter=price_quote.cost_price_per_liter,
                charge_amount=charge_amount,
                cost_amount=cost_amount,
                margin_amount=margin_amount,
                tariff_price_id=price_quote.tariff_price.id,
            )
        )

        totals_entry = totals.setdefault(
            price_quote.currency,
            {"charge": Decimal("0"), "cost": Decimal("0"), "margin": Decimal("0"), "has_cost": True},
        )
        totals_entry["charge"] += charge_amount
        if cost_amount is not None and margin_amount is not None:
            totals_entry["cost"] += cost_amount
            totals_entry["margin"] += margin_amount
        else:
            totals_entry["has_cost"] = False

    totals_by_currency: Dict[str, BillingTotals] = {}
    for currency, data in totals.items():
        totals_by_currency[currency] = BillingTotals(
            charge_amount=data["charge"],
            cost_amount=data["cost"] if data.get("has_cost", False) else None,
            margin_amount=data["margin"] if data.get("has_cost", False) else None,
        )

    return BillingCalculationResult(
        client_id=client_id,
        totals_by_currency=totals_by_currency,
        items=items,
    )


async def build_billing_summary_for_date(billing_date: date) -> None:
    """
    Aggregate operations for the given date and upsert billing summaries.

    The aggregation groups by client, merchant, product type and currency
    and calculates totals for amounts, quantities, operation counts and
    commission (1% of the total amount).
    """

    session = get_sessionmaker()()

    start_ts = datetime.combine(billing_date, datetime.min.time())
    end_ts = datetime.combine(billing_date, datetime.max.time())

    amount_case = case(
        (Operation.status == OperationStatus.COMPLETED, Operation.amount),
        (
            Operation.status.in_([OperationStatus.REFUNDED, OperationStatus.REVERSED]),
            -Operation.amount,
        ),
        else_=0,
    )

    quantity_case = case(
        (Operation.status == OperationStatus.COMPLETED, Operation.quantity),
        (
            Operation.status.in_([OperationStatus.REFUNDED, OperationStatus.REVERSED]),
            -Operation.quantity,
        ),
        else_=0,
    )

    try:
        with session.begin():
            aggregates = (
                session.query(
                    Operation.client_id,
                    Operation.merchant_id,
                    Operation.product_type,
                    Operation.currency,
                    func.coalesce(func.sum(amount_case), 0).label("total_amount"),
                    func.sum(quantity_case).label("total_quantity"),
                    func.count().label("operations_count"),
                )
                .filter(
                    Operation.status.in_(
                        [
                            OperationStatus.COMPLETED,
                            OperationStatus.REFUNDED,
                            OperationStatus.REVERSED,
                        ]
                    )
                )
                .filter(Operation.created_at >= start_ts)
                .filter(Operation.created_at <= end_ts)
                .group_by(
                    Operation.client_id,
                    Operation.merchant_id,
                    Operation.product_type,
                    Operation.currency,
                )
                .all()
            )

            if not aggregates:
                return

            existing = {
                (
                    item.client_id,
                    item.merchant_id,
                    item.product_type,
                    item.currency,
                ): item
                for item in session.query(BillingSummary)
                .filter(BillingSummary.billing_date == billing_date)
                .all()
            }

            for aggregate in aggregates:
                key = (
                    aggregate.client_id,
                    aggregate.merchant_id,
                    aggregate.product_type,
                    aggregate.currency,
                )

                total_amount = int(aggregate.total_amount or 0)
                total_quantity = aggregate.total_quantity
                operations_count = int(aggregate.operations_count or 0)
                commission_amount = int(total_amount * 0.01)

                summary = existing.get(key)
                if summary:
                    summary.total_amount = total_amount
                    summary.total_captured_amount = total_amount
                    summary.total_quantity = total_quantity
                    summary.operations_count = operations_count
                    summary.commission_amount = commission_amount
                else:
                    summary = BillingSummary(
                        billing_date=billing_date,
                        client_id=aggregate.client_id,
                        merchant_id=aggregate.merchant_id,
                        product_type=aggregate.product_type,
                        currency=aggregate.currency,
                        total_amount=total_amount,
                        total_captured_amount=total_amount,
                        total_quantity=total_quantity,
                        operations_count=operations_count,
                        commission_amount=commission_amount,
                    )
                    session.add(summary)

    finally:
        session.close()


def get_billing_summaries(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    client_id: str | None = None,
    merchant_id: str | None = None,
    product_type: ProductType | None = None,
    currency: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[BillingSummary], int]:
    query = (
        db.query(BillingSummary)
        .filter(BillingSummary.billing_date >= date_from)
        .filter(BillingSummary.billing_date <= date_to)
    )

    if client_id:
        query = query.filter(BillingSummary.client_id == client_id)
    if merchant_id:
        query = query.filter(BillingSummary.merchant_id == merchant_id)
    if product_type:
        query = query.filter(BillingSummary.product_type == product_type)
    if currency:
        query = query.filter(BillingSummary.currency == currency)

    total = query.count()

    items = (
        query.order_by(
            BillingSummary.billing_date,
            BillingSummary.client_id,
            BillingSummary.merchant_id,
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return items, total


def build_invoice_data_for_client(
    db: Session,
    *,
    client_id: str,
    period_from: date,
    period_to: date,
    options: dict | None = None,
) -> BillingInvoiceData | None:
    """Aggregate operations for a client and convert them to invoice data."""

    start_ts = datetime.combine(period_from, datetime.min.time())
    end_ts = datetime.combine(period_to, datetime.max.time())

    operations = (
        db.query(Operation)
        .filter(Operation.client_id == client_id)
        .filter(Operation.created_at >= start_ts)
        .filter(Operation.created_at <= end_ts)
        .filter(Operation.status == OperationStatus.COMPLETED)
        .all()
    )

    if not operations:
        return None

    tax_rate = Decimal(str((options or {}).get("tax_rate", 0)))

    lines: list[BillingLineData] = []
    currency = None
    for op in operations:
        currency = currency or op.currency
        amount = int(op.amount or 0)
        tax_amount = int((Decimal(amount) * tax_rate).to_integral_value()) if tax_rate else 0

        lines.append(
            BillingLineData(
                product_id=op.product_id or "unknown",
                liters=op.quantity,
                unit_price=op.unit_price,
                line_amount=amount,
                tax_amount=tax_amount,
                operation_id=str(op.id),
                card_id=op.card_id,
            )
        )

    return BillingInvoiceData(
        client_id=str(client_id),
        period_from=period_from,
        period_to=period_to,
        currency=currency or "RUB",
        lines=lines,
        status=(options or {}).get("status", InvoiceStatus.DRAFT),
    )


def generate_invoices_for_period(
    db: Session,
    *,
    period_from: date,
    period_to: date,
    status: InvoiceStatus = InvoiceStatus.DRAFT,
    options: dict | None = None,
) -> list[Invoice]:
    """Generate invoices for all active clients with tariffs for the given period."""

    billing_metrics.start_run(str(period_from), str(period_to))
    repo = BillingRepository(db)
    clients = (
        db.query(Client)
        .filter(Client.status == "ACTIVE")
        .filter(Client.tariff_plan.isnot(None))
        .all()
    )

    created: list[Invoice] = []
    period_key = f"{period_from}:{period_to}"

    for client in clients:
        try:
            existing = (
                db.query(Invoice)
                .filter(Invoice.client_id == str(client.id))
                .filter(Invoice.period_from == period_from)
                .filter(Invoice.period_to == period_to)
                .filter(Invoice.status != InvoiceStatus.CANCELLED)
                .first()
            )
            if existing:
                continue

            invoice_data = build_invoice_data_for_client(
                db,
                client_id=str(client.id),
                period_from=period_from,
                period_to=period_to,
                options={**(options or {}), "status": status},
            )

            if invoice_data is None:
                continue

            invoice = repo.create_invoice(invoice_data, auto_commit=True)
            billing_metrics.mark_generated()
            billing_metrics.observe_billed_amount(
                invoice.total_with_tax or invoice.total_amount or 0, period_key=period_key
            )
            logger.info(
                "billing.invoice_generated",
                extra={
                    "client_id": str(client.id),
                    "period_from": str(period_from),
                    "period_to": str(period_to),
                    "status": invoice.status,
                    "total_with_tax": invoice.total_with_tax,
                },
            )
            created.append(invoice)
        except Exception:
            billing_metrics.mark_error()
            logger.exception(
                "billing.invoice_generation_failed",
                extra={
                    "client_id": str(client.id),
                    "period_from": str(period_from),
                    "period_to": str(period_to),
                },
            )

    return created


try:
    from app.celery_client import celery_client
except Exception:  # pragma: no cover - optional celery integration
    celery_client = None


if celery_client:
    @celery_client.task(name="billing.generate_monthly_invoices")
    def billing_generate_monthly_invoices(period_from: str, period_to: str) -> list[str]:
        """Celery entrypoint to generate invoices for a period."""

        from datetime import date as _date

        start = _date.fromisoformat(period_from)
        end = _date.fromisoformat(period_to)

        session = get_sessionmaker()()
        try:
            invoices = generate_invoices_for_period(
                session, period_from=start, period_to=end, status=InvoiceStatus.ISSUED
            )
            return [invoice.id for invoice in invoices]
        finally:
            session.close()
