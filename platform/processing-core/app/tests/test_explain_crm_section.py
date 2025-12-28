from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.billing_period import BillingPeriod, BillingPeriodType
from app.models.crm import (
    CRMBillingCycle,
    CRMBillingPeriod,
    CRMFeatureFlag,
    CRMFeatureFlagType,
    CRMSubscription,
    CRMSubscriptionStatus,
    CRMUsageCounter,
    CRMUsageMetric,
    CRMTariffPlan,
    CRMTariffStatus,
)
from app.models.invoice import Invoice
from app.services.explain.unified import build_unified_explain


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_crm_section_from_subscription(session):
    tariff = CRMTariffPlan(
        id="enterprise_fuel_v4",
        name="Enterprise Fuel",
        status=CRMTariffStatus.ACTIVE,
        billing_period=CRMBillingPeriod.MONTHLY,
        base_fee_minor=0,
        currency="RUB",
    )
    subscription = CRMSubscription(
        tenant_id=1,
        client_id="client-1",
        tariff_plan_id=tariff.id,
        status=CRMSubscriptionStatus.ACTIVE,
        billing_cycle=CRMBillingCycle.MONTHLY,
        billing_day=1,
        started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        meta={"crm_effect": {"allowed": False, "reason": "Тариф не включает ночные заправки"}},
    )
    period = BillingPeriod(
        period_type=BillingPeriodType.MONTHLY,
        start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_at=datetime(2025, 1, 31, 23, 59, tzinfo=timezone.utc),
        tz="Europe/Moscow",
    )
    invoice = Invoice(
        client_id="client-1",
        period_from=period.start_at.date(),
        period_to=period.end_at.date(),
        currency="RUB",
        billing_period_id=period.id,
    )
    session.add_all([tariff, subscription, period, invoice])
    session.flush()

    usage_fuel = CRMUsageCounter(
        subscription_id=subscription.id,
        billing_period_id=period.id,
        metric=CRMUsageMetric.FUEL_TX_COUNT,
        value=124,
    )
    usage_drivers = CRMUsageCounter(
        subscription_id=subscription.id,
        billing_period_id=period.id,
        metric=CRMUsageMetric.DRIVERS_COUNT,
        value=12,
    )
    flag_fuel = CRMFeatureFlag(
        tenant_id=1,
        client_id="client-1",
        feature=CRMFeatureFlagType.FUEL_ENABLED,
        enabled=True,
    )
    flag_logistics = CRMFeatureFlag(
        tenant_id=1,
        client_id="client-1",
        feature=CRMFeatureFlagType.LOGISTICS_ENABLED,
        enabled=True,
    )
    session.add_all([usage_fuel, usage_drivers, flag_fuel, flag_logistics])
    session.commit()

    payload = build_unified_explain(session, invoice_id=invoice.id)
    crm_payload = payload["crm"]

    assert crm_payload["tariff"] == {"id": "enterprise_fuel_v4", "name": "Enterprise Fuel"}
    assert crm_payload["subscription"] == {"status": "ACTIVE", "period": "2025-01"}
    assert crm_payload["metrics_used"] == {"fuel_tx_count": 124, "drivers": 12}
    assert crm_payload["feature_flags"] == ["FUEL_ENABLED", "LOGISTICS_ENABLED"]
    assert payload["crm_effect"] == {"allowed": False, "reason": "Тариф не включает ночные заправки"}
