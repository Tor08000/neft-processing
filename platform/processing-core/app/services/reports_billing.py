from __future__ import annotations

from datetime import date, datetime
from typing import Iterable
import hashlib
import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billing_summary import BillingSummary, BillingSummaryStatus
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
        op_date = aggregate.op_date
        if isinstance(op_date, str):
            op_date = date.fromisoformat(op_date)

        key = (op_date, aggregate.merchant_id)
        summary = existing.get(key)

        payload = {
            "date": op_date.isoformat(),
            "merchant_id": aggregate.merchant_id,
            "total_captured_amount": int(aggregate.total_amount or 0),
            "operations_count": int(aggregate.total_operations or 0),
        }
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

        if summary is None:
            summary = BillingSummary(
                date=op_date,
                merchant_id=aggregate.merchant_id,
                total_captured_amount=payload["total_captured_amount"],
                operations_count=payload["operations_count"],
                status=BillingSummaryStatus.PENDING,
                hash=payload_hash,
                generated_at=datetime.utcnow(),
            )
            db.add(summary)
        else:
            summary.date = op_date
            summary.total_captured_amount = payload["total_captured_amount"]
            summary.operations_count = payload["operations_count"]
            summary.status = BillingSummaryStatus.PENDING
            summary.hash = payload_hash
            summary.generated_at = datetime.utcnow()
            summary.finalized_at = None

        result.append(summary)

    db.commit()

    for item in result:
        db.refresh(item)

    return result


def finalize_billing_summary(db: Session, summary_id: str) -> BillingSummary:
    summary = db.query(BillingSummary).filter(BillingSummary.id == summary_id).first()
    if summary is None:
        raise ValueError("summary not found")
    summary.status = BillingSummaryStatus.FINALIZED
    summary.finalized_at = datetime.utcnow()
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


def get_or_build_summary(
    db: Session,
    date_from: date,
    date_to: date,
    merchant_id: str | None = None,
    status: str | None = None,
) -> list[BillingSummary]:
    summaries = list_billing_summaries(
        db, date_from=date_from, date_to=date_to, merchant_id=merchant_id, status=status
    )
    if summaries:
        return summaries
    return build_billing_summary_for_date(
        db, date_from=date_from, date_to=date_to, merchant_id=merchant_id
    )


def list_billing_summaries(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    merchant_id: str | None = None,
    status: str | None = None,
) -> list[BillingSummary]:
    query = (
        db.query(BillingSummary)
        .filter(BillingSummary.date >= date_from)
        .filter(BillingSummary.date <= date_to)
    )

    if merchant_id:
        query = query.filter(BillingSummary.merchant_id == merchant_id)
    if status:
        query = query.filter(BillingSummary.status == status)

    return query.order_by(BillingSummary.date).all()
