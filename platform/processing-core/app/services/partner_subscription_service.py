from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.partner_subscriptions import (
    PartnerBillingCycle,
    PartnerPlan,
    PartnerSubscription,
    PartnerSubscriptionStatus,
)


FREE_PLAN_CODE = "FREE"


class PartnerSubscriptionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def list_plans(self) -> list[PartnerPlan]:
        return self.db.query(PartnerPlan).order_by(PartnerPlan.plan_code.asc()).all()

    def get_active_subscription(self, *, partner_id: str) -> PartnerSubscription | None:
        return (
            self.db.query(PartnerSubscription)
            .filter(PartnerSubscription.partner_id == partner_id)
            .filter(PartnerSubscription.status == PartnerSubscriptionStatus.ACTIVE.value)
            .order_by(PartnerSubscription.started_at.desc())
            .one_or_none()
        )

    def ensure_subscription(self, *, partner_id: str) -> PartnerSubscription:
        subscription = self.get_active_subscription(partner_id=partner_id)
        if subscription:
            return subscription
        plan = self.db.get(PartnerPlan, FREE_PLAN_CODE)
        if not plan:
            plan = PartnerPlan(
                plan_code=FREE_PLAN_CODE,
                title="Free",
                description="Marketplace free plan",
                base_commission=Decimal("0"),
                monthly_fee=Decimal("0"),
                features={
                    "can_create_discounts": False,
                    "can_access_analytics": False,
                    "can_use_recommendations": False,
                    "priority_rank": 0,
                },
                limits={"products": 10},
            )
            self.db.add(plan)
            self.db.flush()
        subscription = PartnerSubscription(
            id=new_uuid_str(),
            partner_id=partner_id,
            plan_code=plan.plan_code,
            status=PartnerSubscriptionStatus.ACTIVE.value,
            started_at=self._now(),
            billing_cycle=PartnerBillingCycle.MONTHLY.value,
            commission_rate=plan.base_commission,
            features=plan.features,
        )
        self.db.add(subscription)
        self.db.flush()
        return subscription
