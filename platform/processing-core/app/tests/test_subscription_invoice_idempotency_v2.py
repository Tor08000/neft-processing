from datetime import datetime, timezone

from app.db.types import new_uuid_str
from app.models.crm import (
    CRMBillingCycle,
    CRMSubscription,
    CRMSubscriptionPeriodSegment,
    CRMSubscriptionSegmentReason,
    CRMSubscriptionSegmentStatus,
    CRMSubscriptionStatus,
    CRMUsageCounter,
    CRMUsageMetric,
)
from app.services.crm.subscription_pricing_engine import price_subscription_v2


def test_charge_key_contains_segment_and_metric() -> None:
    subscription = CRMSubscription(
        id="sub-1",
        tenant_id=1,
        client_id="client-1",
        tariff_plan_id="tariff-basic",
        status=CRMSubscriptionStatus.ACTIVE,
        billing_cycle=CRMBillingCycle.MONTHLY,
        billing_day=1,
        started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
    segment = CRMSubscriptionPeriodSegment(
        id=new_uuid_str(),
        subscription_id=subscription.id,
        billing_period_id=new_uuid_str(),
        tariff_plan_id="tariff-basic",
        segment_start=period_start,
        segment_end=period_end,
        status=CRMSubscriptionSegmentStatus.ACTIVE,
        days_count=31,
        reason=CRMSubscriptionSegmentReason.START,
    )
    counters = [
        CRMUsageCounter(
            subscription_id=subscription.id,
            billing_period_id="period-1",
            segment_id=segment.id,
            metric=CRMUsageMetric.FUEL_TX_COUNT,
            value=12,
        )
    ]
    pricing = price_subscription_v2(
        subscription=subscription,
        billing_period_id="period-1",
        segments=[segment],
        counters=counters,
        tariff_definition={
            "version": 2,
            "base_fee": {"amount_minor": 1000, "currency": "RUB"},
            "included": [{"metric": "FUEL_TX_COUNT", "value": 10, "proration": "DAILY"}],
            "overage": [{"metric": "FUEL_TX_COUNT", "unit_price_minor": 50}],
        },
        period_start=period_start,
        period_end=period_end,
    )
    charge_keys = {charge.charge_key for charge in pricing.charges}
    assert any(key.startswith("sub:sub-1:period:period-1:seg:2024-01-01-2024-01-31") for key in charge_keys)
