from datetime import datetime, timezone

from app.db.types import new_uuid_str
from app.models.crm import (
    CRMBillingCycle,
    CRMSubscription,
    CRMSubscriptionPeriodSegment,
    CRMSubscriptionSegmentReason,
    CRMSubscriptionSegmentStatus,
    CRMSubscriptionStatus,
)
from app.services.crm.subscription_pricing_engine import price_subscription_v2


def test_proration_base_fee_v2() -> None:
    subscription = CRMSubscription(
        id=new_uuid_str(),
        tenant_id=1,
        client_id="client-1",
        tariff_plan_id="tariff-basic",
        status=CRMSubscriptionStatus.ACTIVE,
        billing_cycle=CRMBillingCycle.MONTHLY,
        billing_day=1,
        started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 30, 23, 59, 59, tzinfo=timezone.utc)
    segment = CRMSubscriptionPeriodSegment(
        id=new_uuid_str(),
        subscription_id=subscription.id,
        billing_period_id=new_uuid_str(),
        tariff_plan_id="tariff-basic",
        segment_start=period_start,
        segment_end=datetime(2024, 1, 15, 23, 59, 59, tzinfo=timezone.utc),
        status=CRMSubscriptionSegmentStatus.ACTIVE,
        days_count=15,
        reason=CRMSubscriptionSegmentReason.START,
    )
    pricing = price_subscription_v2(
        subscription=subscription,
        billing_period_id="period-1",
        segments=[segment],
        counters=[],
        tariff_definition={
            "version": 2,
            "base_fee": {"amount_minor": 3000, "currency": "RUB"},
            "included": [],
            "overage": [],
        },
        period_start=period_start,
        period_end=period_end,
    )
    assert pricing.charges[0].amount == 1500
