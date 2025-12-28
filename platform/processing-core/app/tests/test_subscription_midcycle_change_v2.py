from datetime import datetime, timezone

from app.models.billing_period import BillingPeriod, BillingPeriodType
from app.models.crm import (
    CRMBillingCycle,
    CRMSubscription,
    CRMSubscriptionSegmentReason,
    CRMSubscriptionSegmentStatus,
    CRMSubscriptionStatus,
)
from app.services.crm.subscription_segments import build_segments_v2


def test_midcycle_tariff_change_builds_two_segments() -> None:
    period = BillingPeriod(
        id="period-1",
        period_type=BillingPeriodType.MONTHLY,
        start_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_at=datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
        tz="UTC",
    )
    subscription = CRMSubscription(
        id="sub-1",
        tenant_id=1,
        client_id="client-1",
        tariff_plan_id="tariff-basic",
        status=CRMSubscriptionStatus.ACTIVE,
        billing_cycle=CRMBillingCycle.MONTHLY,
        billing_day=1,
        started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        meta={
            "v2_events": [
                {
                    "type": "UPGRADE",
                    "effective_at": datetime(2024, 1, 16, tzinfo=timezone.utc).isoformat(),
                    "tariff_plan_id": "tariff-pro",
                }
            ]
        },
    )
    segments = build_segments_v2(subscription=subscription, period=period)
    assert len(segments) == 2
    assert segments[0].tariff_plan_id == "tariff-basic"
    assert segments[1].tariff_plan_id == "tariff-pro"
    assert segments[1].reason == CRMSubscriptionSegmentReason.UPGRADE
    assert segments[0].status == CRMSubscriptionSegmentStatus.ACTIVE
