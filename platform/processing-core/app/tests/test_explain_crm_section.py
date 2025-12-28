from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.crm import (
    CRMBillingCycle,
    CRMBillingMode,
    CRMBillingPeriod,
    CRMClient,
    CRMClientStatus,
    CRMContract,
    CRMContractStatus,
    CRMFeatureFlag,
    CRMFeatureFlagType,
    CRMSubscription,
    CRMSubscriptionStatus,
    CRMTariffPlan,
    CRMTariffStatus,
    CRMUsageCounter,
    CRMUsageMetric,
)
from app.services.crm.decision_context import build_decision_context
from app.services.explain.sources import build_crm_section


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


def test_explain_crm_section_contains_contract_metrics_and_flags(session):
    client = CRMClient(
        id="client-2",
        tenant_id=1,
        legal_name="Client 2",
        country="RU",
        timezone="Europe/Moscow",
        status=CRMClientStatus.ACTIVE,
    )
    contract = CRMContract(
        tenant_id=1,
        client_id="client-2",
        contract_number="C-2",
        status=CRMContractStatus.ACTIVE,
        billing_mode=CRMBillingMode.POSTPAID,
        currency="RUB",
    )
    tariff = CRMTariffPlan(
        id="tariff-pro",
        name="Pro",
        status=CRMTariffStatus.ACTIVE,
        billing_period=CRMBillingPeriod.MONTHLY,
        base_fee_minor=0,
        currency="RUB",
    )
    subscription = CRMSubscription(
        tenant_id=1,
        client_id="client-2",
        tariff_plan_id=tariff.id,
        status=CRMSubscriptionStatus.ACTIVE,
        billing_cycle=CRMBillingCycle.MONTHLY,
        billing_day=1,
        started_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
    )
    session.add_all([client, contract, tariff, subscription])
    session.flush()
    session.add_all(
        [
            CRMFeatureFlag(
                tenant_id=1,
                client_id="client-2",
                feature=CRMFeatureFlagType.FUEL_ENABLED,
                enabled=True,
            ),
            CRMFeatureFlag(
                tenant_id=1,
                client_id="client-2",
                feature=CRMFeatureFlagType.RISK_BLOCKING_ENABLED,
                enabled=False,
            ),
            CRMUsageCounter(
                subscription_id=subscription.id,
                billing_period_id="period-1",
                metric=CRMUsageMetric.FUEL_TX_COUNT,
                value=12,
            ),
            CRMUsageCounter(
                subscription_id=subscription.id,
                billing_period_id="period-1",
                metric=CRMUsageMetric.DRIVERS_COUNT,
                value=3,
            ),
        ]
    )
    session.commit()

    payload = build_crm_section(session, tenant_id=1, client_id="client-2")

    assert payload is not None
    assert payload["tariff"] == "tariff-pro"
    assert payload["contract"]["version"] == contract.crm_contract_version
    assert payload["metrics_used"]["fuel_tx"] == 12
    assert payload["metrics_used"]["drivers"] == 3
    assert payload["feature_flags"]["fuel_enabled"] is True
    assert "FUEL_ENABLED" in payload["decision_flags"]
