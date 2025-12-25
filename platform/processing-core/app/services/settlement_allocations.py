from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.finance import InvoiceSettlementAllocation, SettlementSourceType
from app.services.billing_periods import BillingPeriodService, period_bounds_for_dates


@dataclass(frozen=True)
class SettlementSummaryRow:
    settlement_period_id: str
    period_start: datetime
    period_end: datetime
    currency: str
    total_payments: int
    total_credits: int
    total_refunds: int
    allocations_count: int


def resolve_settlement_period(db: Session, *, event_at: datetime) -> BillingPeriod:
    if event_at.tzinfo is None:
        event_at = event_at.replace(tzinfo=timezone.utc)

    tz = ZoneInfo(settings.NEFT_BILLING_TZ)
    event_date = event_at.astimezone(tz).date()
    start_at, end_at = period_bounds_for_dates(
        date_from=event_date,
        date_to=event_date,
        tz=settings.NEFT_BILLING_TZ,
    )

    period_service = BillingPeriodService(db)
    period = period_service.get_or_create(
        period_type=BillingPeriodType.DAILY,
        start_at=start_at,
        end_at=end_at,
        tz=settings.NEFT_BILLING_TZ,
    )
    if period.status in {BillingPeriodStatus.FINALIZED, BillingPeriodStatus.LOCKED}:
        period = period_service.get_or_create(
            period_type=BillingPeriodType.ADHOC,
            start_at=start_at,
            end_at=end_at,
            tz=settings.NEFT_BILLING_TZ,
        )
    return period


def list_settlement_summary(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    client_id: str | None = None,
) -> list[SettlementSummaryRow]:
    start_at, end_at = period_bounds_for_dates(
        date_from=date_from,
        date_to=date_to,
        tz=settings.NEFT_BILLING_TZ,
    )

    payments_total = func.coalesce(
        func.sum(
            case(
                (InvoiceSettlementAllocation.source_type == SettlementSourceType.PAYMENT, InvoiceSettlementAllocation.amount),
                else_=0,
            )
        ),
        0,
    ).label("total_payments")
    credits_total = func.coalesce(
        func.sum(
            case(
                (
                    InvoiceSettlementAllocation.source_type == SettlementSourceType.CREDIT_NOTE,
                    InvoiceSettlementAllocation.amount,
                ),
                else_=0,
            )
        ),
        0,
    ).label("total_credits")
    refunds_total = func.coalesce(
        func.sum(
            case(
                (InvoiceSettlementAllocation.source_type == SettlementSourceType.REFUND, InvoiceSettlementAllocation.amount),
                else_=0,
            )
        ),
        0,
    ).label("total_refunds")

    query = (
        db.query(
            InvoiceSettlementAllocation.settlement_period_id,
            BillingPeriod.start_at,
            BillingPeriod.end_at,
            InvoiceSettlementAllocation.currency,
            payments_total,
            credits_total,
            refunds_total,
            func.count(InvoiceSettlementAllocation.id).label("allocations_count"),
        )
        .join(BillingPeriod, BillingPeriod.id == InvoiceSettlementAllocation.settlement_period_id)
        .filter(BillingPeriod.start_at >= start_at)
        .filter(BillingPeriod.start_at <= end_at)
    )

    if client_id:
        query = query.filter(InvoiceSettlementAllocation.client_id == client_id)

    rows = (
        query.group_by(
            InvoiceSettlementAllocation.settlement_period_id,
            BillingPeriod.start_at,
            BillingPeriod.end_at,
            InvoiceSettlementAllocation.currency,
        )
        .order_by(BillingPeriod.start_at.asc())
        .all()
    )

    return [
        SettlementSummaryRow(
            settlement_period_id=str(row.settlement_period_id),
            period_start=row.start_at,
            period_end=row.end_at,
            currency=row.currency,
            total_payments=int(row.total_payments or 0),
            total_credits=int(row.total_credits or 0),
            total_refunds=int(row.total_refunds or 0),
            allocations_count=int(row.allocations_count or 0),
        )
        for row in rows
    ]


__all__ = ["SettlementSummaryRow", "list_settlement_summary", "resolve_settlement_period"]
