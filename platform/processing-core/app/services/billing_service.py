from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.operation import ProductType
from app.models.billing_summary import BillingSummary
from app.models.operation import Operation, OperationStatus


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
