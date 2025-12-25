from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType


_ALLOWED_TRANSITIONS = {
    BillingPeriodStatus.OPEN: {BillingPeriodStatus.FINALIZED},
    BillingPeriodStatus.FINALIZED: {BillingPeriodStatus.LOCKED},
    BillingPeriodStatus.LOCKED: set(),
}


def period_bounds_for_dates(
    *,
    date_from: date,
    date_to: date,
    tz: str,
) -> tuple[datetime, datetime]:
    tzinfo = ZoneInfo(tz)
    start = datetime.combine(date_from, time.min).replace(tzinfo=tzinfo)
    end = datetime.combine(date_to, time.max).replace(tzinfo=tzinfo)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


class BillingPeriodConflict(ValueError):
    """Raised when an action is not permitted for billing period state."""


class BillingPeriodService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, *, period_type: BillingPeriodType, start_at: datetime, end_at: datetime, tz: str) -> BillingPeriod:
        period = (
            self.db.query(BillingPeriod)
            .filter(BillingPeriod.period_type == period_type)
            .filter(BillingPeriod.start_at == start_at)
            .filter(BillingPeriod.end_at == end_at)
            .one_or_none()
        )
        if period:
            return period
        period = BillingPeriod(period_type=period_type, start_at=start_at, end_at=end_at, tz=tz)
        self.db.add(period)
        self.db.flush()
        return period

    def get_by_bounds(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        period_type: BillingPeriodType | None = None,
    ) -> BillingPeriod | None:
        query = self.db.query(BillingPeriod).filter(BillingPeriod.start_at == start_at).filter(BillingPeriod.end_at == end_at)
        if period_type:
            query = query.filter(BillingPeriod.period_type == period_type)
        return query.one_or_none()

    @staticmethod
    def require_status(period: BillingPeriod, *, allowed: set[BillingPeriodStatus], action: str) -> None:
        if period.status not in allowed:
            allowed_display = ", ".join(sorted(status.value for status in allowed))
            raise BillingPeriodConflict(
                f"Billing period {period.id} status {period.status.value} not allowed for {action}. Allowed: {allowed_display}"
            )

    @staticmethod
    def require_transition(current: BillingPeriodStatus, target: BillingPeriodStatus) -> None:
        if current == target:
            return
        if target not in _ALLOWED_TRANSITIONS.get(current, set()):
            raise BillingPeriodConflict(
                f"Billing period cannot transition from {current.value} to {target.value}"
            )

    def lock(self, *, period_type: BillingPeriodType, start_at: datetime, end_at: datetime, tz: str) -> BillingPeriod:
        period = self.get_or_create(period_type=period_type, start_at=start_at, end_at=end_at, tz=tz)
        self.require_transition(period.status, BillingPeriodStatus.LOCKED)
        if period.status != BillingPeriodStatus.LOCKED:
            period.status = BillingPeriodStatus.LOCKED
            period.locked_at = datetime.now(timezone.utc)
            self.db.add(period)
            self.db.flush()
        return period

    def finalize(self, *, period_type: BillingPeriodType, start_at: datetime, end_at: datetime, tz: str) -> BillingPeriod:
        period = self.get_or_create(period_type=period_type, start_at=start_at, end_at=end_at, tz=tz)
        self.require_transition(period.status, BillingPeriodStatus.FINALIZED)
        if period.status != BillingPeriodStatus.FINALIZED:
            period.status = BillingPeriodStatus.FINALIZED
            period.finalized_at = datetime.now(timezone.utc)
            self.db.add(period)
            self.db.flush()
        return period

    def list_periods(
        self,
        *,
        status: BillingPeriodStatus | None = None,
        period_type: BillingPeriodType | None = None,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
    ) -> list[BillingPeriod]:
        query = self.db.query(BillingPeriod)
        if status:
            query = query.filter(BillingPeriod.status == status)
        if period_type:
            query = query.filter(BillingPeriod.period_type == period_type)
        if start_from:
            query = query.filter(BillingPeriod.start_at >= start_from)
        if start_to:
            query = query.filter(BillingPeriod.start_at <= start_to)
        return query.order_by(BillingPeriod.start_at.desc()).all()
