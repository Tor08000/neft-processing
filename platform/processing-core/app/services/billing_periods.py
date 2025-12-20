from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType


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

    def lock(self, *, period_type: BillingPeriodType, start_at: datetime, end_at: datetime, tz: str) -> BillingPeriod:
        period = self.get_or_create(period_type=period_type, start_at=start_at, end_at=end_at, tz=tz)
        if period.status == BillingPeriodStatus.FINALIZED:
            raise BillingPeriodConflict("Billing period already finalized")
        if period.status != BillingPeriodStatus.LOCKED:
            period.status = BillingPeriodStatus.LOCKED
            period.locked_at = datetime.now(timezone.utc)
            self.db.add(period)
            self.db.flush()
        return period

    def finalize(self, *, period_type: BillingPeriodType, start_at: datetime, end_at: datetime, tz: str) -> BillingPeriod:
        period = self.get_or_create(period_type=period_type, start_at=start_at, end_at=end_at, tz=tz)
        if period.status == BillingPeriodStatus.OPEN:
            raise BillingPeriodConflict("Billing period must be locked before finalize")
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
