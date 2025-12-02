from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billing_summary import BillingSummary
from app.models.operation import Operation


def _capture_aggregation_query(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    merchant_id: str | None = None,
):
    query = (
        db.query(
            func.date(Operation.created_at).label("op_date"),
            Operation.merchant_id,
            func.coalesce(func.sum(Operation.amount), 0).label("total_amount"),
            func.count().label("total_operations"),
        )
        .filter(Operation.operation_type == "CAPTURE")
        .filter(
            Operation.created_at
            >= datetime.combine(date_from, datetime.min.time(), tzinfo=None)
        )
        .filter(
            Operation.created_at
            <= datetime.combine(date_to, datetime.max.time(), tzinfo=None)
        )
    )

    if merchant_id:
        query = query.filter(Operation.merchant_id == merchant_id)

    return query.group_by("op_date", Operation.merchant_id).order_by("op_date")


def build_billing_summary_for_date(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    merchant_id: str | None = None,
) -> list[BillingSummary]:
    aggregates: Iterable = _capture_aggregation_query(
        db, date_from=date_from, date_to=date_to, merchant_id=merchant_id
    ).all()

    if not aggregates:
        return []

    existing_query = (
        db.query(BillingSummary)
        .filter(BillingSummary.date >= date_from)
        .filter(BillingSummary.date <= date_to)
    )

    if merchant_id:
        existing_query = existing_query.filter(BillingSummary.merchant_id == merchant_id)

    existing = {
        (summary.date, summary.merchant_id): summary for summary in existing_query
    }

    result: list[BillingSummary] = []

    for aggregate in aggregates:
        key = (aggregate.op_date, aggregate.merchant_id)
        summary = existing.get(key)

        if summary is None:
            summary = BillingSummary(
                date=aggregate.op_date,
                merchant_id=aggregate.merchant_id,
                total_captured_amount=int(aggregate.total_amount or 0),
                operations_count=int(aggregate.total_operations or 0),
            )
            db.add(summary)
        else:
            summary.total_captured_amount = int(aggregate.total_amount or 0)
            summary.operations_count = int(aggregate.total_operations or 0)

        result.append(summary)

    db.commit()

    for item in result:
        db.refresh(item)

    return result


def list_billing_summaries(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    merchant_id: str | None = None,
) -> list[BillingSummary]:
    query = (
        db.query(BillingSummary)
        .filter(BillingSummary.date >= date_from)
        .filter(BillingSummary.date <= date_to)
    )

    if merchant_id:
        query = query.filter(BillingSummary.merchant_id == merchant_id)

    return query.order_by(BillingSummary.date).all()
