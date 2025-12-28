from __future__ import annotations

from contextlib import nullcontext
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_sessionmaker
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.billing_period import BillingPeriodStatus, BillingPeriodType
from app.models.fuel import FuelTransaction, FuelTransactionStatus, FuelType
from app.models.operation import Operation, OperationStatus
from app.models.operation import ProductType
from app.models.billing_job_run import BillingJobRun, BillingJobStatus, BillingJobType
from app.services.billing_job_runs import BillingJobRunService
from app.services.billing_metrics import metrics as billing_metrics
from app.services.billing_periods import BillingPeriodConflict, BillingPeriodService, period_bounds_for_dates
from app.services.billing_summary_hash import hash_payload
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)

BILLABLE_STATUSES = {
    OperationStatus.CAPTURED,
    OperationStatus.COMPLETED,
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


def _aggregate_operations(session: Session, billing_date: date) -> list[dict]:
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

    rows = (
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
    return [
        {
            "client_id": row.client_id,
            "merchant_id": row.merchant_id,
            "product_type": row.product_type,
            "currency": row.currency,
            "total_amount": int(row.total_amount or 0),
            "total_quantity": row.total_quantity,
            "operations_count": int(row.operations_count or 0),
        }
        for row in rows
    ]


def _fuel_product_type(value: FuelType | str | None) -> ProductType | None:
    if value is None:
        return None
    normalized = value.value if hasattr(value, "value") else str(value)
    if normalized == "AI-92":
        return ProductType.AI92
    if normalized == "AI-95":
        return ProductType.AI95
    if normalized == "AI-98":
        return ProductType.AI98
    return ProductType.__members__.get(normalized.replace("-", ""), ProductType.OTHER)


def _aggregate_fuel_transactions(session: Session, billing_date: date) -> list[dict]:
    start_ts, end_ts = _billing_window(billing_date)
    rows = (
        session.query(
            FuelTransaction.client_id,
            FuelTransaction.network_id.label("merchant_id"),
            FuelTransaction.fuel_type,
            FuelTransaction.currency,
            func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0).label("total_amount"),
            func.coalesce(func.sum(FuelTransaction.volume_ml), 0).label("total_volume"),
            func.count().label("operations_count"),
        )
        .filter(FuelTransaction.status == FuelTransactionStatus.SETTLED)
        .filter(FuelTransaction.occurred_at >= start_ts)
        .filter(FuelTransaction.occurred_at <= end_ts)
        .group_by(
            FuelTransaction.client_id,
            FuelTransaction.network_id,
            FuelTransaction.fuel_type,
            FuelTransaction.currency,
        )
        .all()
    )
    aggregates: list[dict] = []
    for row in rows:
        aggregates.append(
            {
                "client_id": row.client_id,
                "merchant_id": row.merchant_id,
                "product_type": _fuel_product_type(row.fuel_type),
                "currency": row.currency,
                "total_amount": int(row.total_amount or 0),
                "total_quantity": Decimal(row.total_volume or 0) / Decimal("1000"),
                "operations_count": int(row.operations_count or 0),
            }
        )
    return aggregates


def _upsert_billing_summaries(
    session: Session,
    *,
    billing_date: date,
    billing_period_id: str,
) -> list[BillingSummary]:
    aggregates = _aggregate_operations(session, billing_date)
    aggregates.extend(_aggregate_fuel_transactions(session, billing_date))
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
        for item in (
            session.query(BillingSummary)
            .filter(BillingSummary.billing_date == billing_date)
            .filter(BillingSummary.billing_period_id == billing_period_id)
            .all()
        )
    }

    updated_items: list[BillingSummary] = []
    now = datetime.utcnow()

    for aggregate in aggregates:
        key = (
            aggregate["client_id"],
            aggregate["merchant_id"],
            aggregate["product_type"],
            aggregate["currency"],
        )

        total_amount = int(aggregate["total_amount"] or 0)
        total_quantity = aggregate["total_quantity"]
        operations_count = int(aggregate["operations_count"] or 0)
        commission_amount = _commission(total_amount)
        payload_hash = hash_payload(
            {
                "billing_date": billing_date,
                "billing_period_id": billing_period_id,
                "client_id": aggregate["client_id"],
                "merchant_id": aggregate["merchant_id"],
                "product_type": aggregate["product_type"],
                "currency": aggregate["currency"],
                "total_amount": total_amount,
                "total_quantity": total_quantity,
                "operations_count": operations_count,
                "commission_amount": commission_amount,
            }
        )

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
            summary.hash = payload_hash
        else:
            summary = BillingSummary(
                billing_date=billing_date,
                billing_period_id=billing_period_id,
                client_id=aggregate["client_id"],
                merchant_id=aggregate["merchant_id"],
                product_type=aggregate["product_type"],
                currency=aggregate["currency"],
                total_amount=total_amount,
                total_captured_amount=total_amount,
                total_quantity=total_quantity,
                operations_count=operations_count,
                commission_amount=commission_amount,
                status=BillingSummaryStatus.PENDING,
                generated_at=now,
                hash=payload_hash,
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
    job_service = BillingJobRunService(session)
    txn_context = nullcontext() if session.in_transaction() else session.begin()

    logger.info(
        "billing.daily.start",
        extra={
            "billing_date": str(billing_date),
            "enabled": settings.NEFT_BILLING_DAILY_ENABLED,
        },
    )

    job_run: BillingJobRun | None = None

    try:
        with txn_context:
            job_run = job_service.start(
                BillingJobType.BILLING_DAILY,
                params={"billing_date": str(billing_date)},
            )

            if not settings.NEFT_BILLING_DAILY_ENABLED:
                logger.info("billing.daily.disabled")
                result = job_service.succeed(
                    job_run, metrics={"processed": 0, "billing_date": str(billing_date), "enabled": False}
                )
                billing_metrics.mark_daily_run(BillingJobStatus.SUCCESS.value, duration_ms=result.duration_ms)
                return []

            period_service = BillingPeriodService(session)
            period_start, period_end = period_bounds_for_dates(
                date_from=billing_date,
                date_to=billing_date,
                tz=settings.NEFT_BILLING_TZ,
            )
            period = period_service.get_or_create(
                period_type=BillingPeriodType.DAILY,
                start_at=period_start,
                end_at=period_end,
                tz=settings.NEFT_BILLING_TZ,
            )
            if period.status != BillingPeriodStatus.OPEN:
                raise BillingPeriodConflict(f"Billing period {period.id} is {period.status.value}")

            summaries = _upsert_billing_summaries(
                session,
                billing_date=billing_date,
                billing_period_id=str(period.id),
            )
            result = job_service.succeed(
                job_run,
                metrics={"processed": len(summaries), "billing_date": str(billing_date)},
            )
            billing_metrics.mark_daily_run(BillingJobStatus.SUCCESS.value, duration_ms=result.duration_ms)
        logger.info(
            "billing.daily.completed",
            extra={
                "billing_date": str(billing_date),
                "processed": len(summaries),
            },
        )
        return summaries
    except Exception as exc:  # noqa: BLE001
        result = job_service.fail(job_run, error=str(exc)) if job_run else None
        billing_metrics.mark_daily_run(
            BillingJobStatus.FAILED.value, duration_ms=result.duration_ms if result else None
        )
        raise
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
    job_service = BillingJobRunService(session)
    txn_context = nullcontext() if session.in_transaction() else session.begin()

    tz = ZoneInfo(settings.NEFT_BILLING_TZ)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(tz)
    cutoff = datetime.combine(billing_date, time.max).replace(tzinfo=tz) + timedelta(
        hours=settings.NEFT_BILLING_FINALIZE_GRACE_HOURS
    )
    job_run: BillingJobRun | None = None

    if current <= cutoff:
        logger.info(
            "billing.finalize.skipped",
            extra={"billing_date": str(billing_date), "now": current.isoformat(), "cutoff": cutoff.isoformat()},
        )
        with txn_context:
            job_run = job_service.start(
                BillingJobType.BILLING_FINALIZE,
                params={"billing_date": str(billing_date)},
            )
            result = job_service.succeed(
                job_run,
                metrics={"updated": 0, "billing_date": str(billing_date), "skipped": True},
            )
        billing_metrics.mark_finalize_run(BillingJobStatus.SUCCESS.value, duration_ms=result.duration_ms)
        if should_close:
            session.close()
        return 0

    logger.info("billing.finalize.start", extra={"billing_date": str(billing_date)})
    try:
        with txn_context:
            job_run = job_service.start(
                BillingJobType.BILLING_FINALIZE,
                params={"billing_date": str(billing_date)},
            )
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
            result = job_service.succeed(
                job_run,
                metrics={"updated": int(updated or 0), "billing_date": str(billing_date)},
            )
            billing_metrics.mark_finalize_run(BillingJobStatus.SUCCESS.value, duration_ms=result.duration_ms)
        logger.info("billing.finalize.completed", extra={"billing_date": str(billing_date), "updated": updated})
        return int(updated or 0)
    except Exception as exc:  # noqa: BLE001
        result = job_service.fail(job_run, error=str(exc)) if job_run else None
        billing_metrics.mark_finalize_run(
            BillingJobStatus.FAILED.value, duration_ms=result.duration_ms if result else None
        )
        raise
    finally:
        if should_close:
            session.close()
