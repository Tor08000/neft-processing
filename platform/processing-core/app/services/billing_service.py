from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.operation import OperationType, ProductType
from app.models.billing_summary import BillingSummary
from app.models.operation import Operation, OperationStatus
from app.services.pricing_service import PriceQuote, get_effective_price


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

    session = SessionLocal()

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
