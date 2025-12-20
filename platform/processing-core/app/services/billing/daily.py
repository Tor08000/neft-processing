from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_sessionmaker
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.operation import Operation, OperationStatus
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)

BILLABLE_STATUSES = {
    OperationStatus.CAPTURED,
    OperationStatus.COMPLETED,
    OperationStatus.REFUNDED,
    OperationStatus.REVERSED,
}


def _billing_window(billing_date: date) -> tuple[datetime, datetime]:
    tz = ZoneInfo(settings.NEFT_BILLING_TZ)
    start = datetime.combine(billing_date, time.min).replace(tzinfo=tz)
    end = datetime.combine(billing_date, time.max).replace(tzinfo=tz)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _default_billing_date(now: datetime | None = None) -> date:
    tz = ZoneInfo(settings.NEFT_BILLING_TZ)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(tz)
    return (current.date() - timedelta(days=1))


def _commission(amount: int) -> int:
    rate = Decimal(str(settings.NEFT_COMMISSION_RATE))
    return int((Decimal(amount) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _aggregate_operations(session: Session, billing_date: date):
    start_ts, end_ts = _billing_window(billing_date)

    amount_value = func.coalesce(
        func.nullif(Operation.amount_settled, 0),
        func.nullif(Operation.captured_amount, 0),
        Operation.amount_original,
    )
    refund_delta = func.coalesce(Operation.refunded_amount, 0)
    net_amount = case(
        (Operation.status.in_({OperationStatus.REFUNDED, OperationStatus.REVERSED}), -amount_value),
        else_=amount_value - refund_delta,
    )
    net_quantity = case(
        (Operation.status.in_({OperationStatus.REFUNDED, OperationStatus.REVERSED}), -Operation.quantity),
        else_=Operation.quantity,
    )

    return (
        session.query(
            Operation.client_id,
            Operation.merchant_id,
            Operation.product_type,
            Operation.currency,
            func.coalesce(func.sum(net_amount), 0).label("total_amount"),
            func.sum(net_quantity).label("total_quantity"),
            func.count().label("operations_count"),
        )
        .filter(Operation.status.in_(BILLABLE_STATUSES))
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


def _upsert_billing_summaries(session: Session, billing_date: date) -> list[BillingSummary]:
    aggregates = _aggregate_operations(session, billing_date)
    if not aggregates:
        logger.info("billing.daily.no_operations", extra={"billing_date": str(billing_date)})
        return []

    existing = {
        (
            item.client_id,
            item.merchant_id,
            item.product_type,
            item.currency,
        ): item
        for item in session.query(BillingSummary).filter(BillingSummary.billing_date == billing_date).all()
    }

    updated_items: list[BillingSummary] = []
    now = datetime.utcnow()

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
        commission_amount = _commission(total_amount)

        summary = existing.get(key)
        if summary and summary.status == BillingSummaryStatus.FINALIZED:
            continue

        if summary:
            summary.total_amount = total_amount
            summary.total_captured_amount = total_amount
            summary.total_quantity = total_quantity
            summary.operations_count = operations_count
            summary.commission_amount = commission_amount
            summary.generated_at = now
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
                status=BillingSummaryStatus.PENDING,
                generated_at=now,
            )
            session.add(summary)
        updated_items.append(summary)

    return updated_items


def run_billing_daily(
    target_date: date | None = None,
    *,
    session: Session | None = None,
    now: datetime | None = None,
) -> list[BillingSummary]:
    """Aggregate operations for the billing date and store PENDING summaries."""

    billing_date = target_date or _default_billing_date(now)
    should_close = session is None
    session = session or get_sessionmaker()()

    logger.info(
        "billing.daily.start",
        extra={
            "billing_date": str(billing_date),
            "enabled": settings.NEFT_BILLING_DAILY_ENABLED,
        },
    )

    if not settings.NEFT_BILLING_DAILY_ENABLED:
        logger.info("billing.daily.disabled")
        if should_close:
            session.close()
        return []

    try:
        with session.begin():
            summaries = _upsert_billing_summaries(session, billing_date)
        logger.info(
            "billing.daily.completed",
            extra={
                "billing_date": str(billing_date),
                "processed": len(summaries),
            },
        )
        return summaries
    finally:
        if should_close:
            session.close()


def finalize_billing_day(
    billing_date: date,
    *,
    session: Session | None = None,
    now: datetime | None = None,
) -> int:
    """Finalize PENDING billing summaries once grace period is over."""

    should_close = session is None
    session = session or get_sessionmaker()()

    tz = ZoneInfo(settings.NEFT_BILLING_TZ)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(tz)
    cutoff = datetime.combine(billing_date, time.max).replace(tzinfo=tz) + timedelta(
        hours=settings.NEFT_BILLING_FINALIZE_GRACE_HOURS
    )

    if current <= cutoff:
        logger.info(
            "billing.finalize.skipped",
            extra={"billing_date": str(billing_date), "now": current.isoformat(), "cutoff": cutoff.isoformat()},
        )
        if should_close:
            session.close()
        return 0

    logger.info("billing.finalize.start", extra={"billing_date": str(billing_date)})
    try:
        with session.begin():
            updated = (
                session.query(BillingSummary)
                .filter(BillingSummary.billing_date == billing_date)
                .filter(BillingSummary.status == BillingSummaryStatus.PENDING)
                .update(
                    {
                        "status": BillingSummaryStatus.FINALIZED,
                        "finalized_at": datetime.utcnow(),
                    },
                    synchronize_session=False,
                )
            )
        logger.info("billing.finalize.completed", extra={"billing_date": str(billing_date), "updated": updated})
        return int(updated or 0)
    finally:
        if should_close:
            session.close()
