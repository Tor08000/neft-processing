from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.crm import (
    CRMBillingCycle,
    CRMBillingPeriod,
    CRMClient,
    CRMClientStatus,
    CRMFeatureFlag,
    CRMFeatureFlagType,
    CRMSubscription,
    CRMSubscriptionStatus,
    CRMTariffPlan,
    CRMTariffStatus,
)
from app.services.crm.decision_context import build_decision_context


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


def test_decision_context_from_subscription(session):
    client = CRMClient(
        id="client-1",
        tenant_id=1,
        legal_name="Client",
        country="RU",
        timezone="Europe/Moscow",
        status=CRMClientStatus.ACTIVE,
    )
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
    session.add_all([client, tariff, subscription])
    session.flush()
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
    session.add_all([flag_fuel, flag_logistics])
    session.commit()

    payload = build_decision_context(session, tenant_id=1, client_id="client-1")

    assert payload["tariff"].id == "enterprise_fuel_v4"
    assert payload["tariff"].name == "Enterprise Fuel"
    assert {flag.feature.value for flag in payload["feature_flags"]} == {"FUEL_ENABLED", "LOGISTICS_ENABLED"}
    assert payload["enforcement_flags"]["fuel_enabled"] is True
    assert payload["enforcement_flags"]["logistics_enabled"] is True
