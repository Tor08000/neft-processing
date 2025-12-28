from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.crm import (
    CRMBillingCycle,
    CRMClient,
    CRMClientStatus,
    CRMContract,
    CRMContractStatus,
    CRMFeatureFlag,
    CRMFeatureFlagType,
    CRMLimitProfile,
    CRMProfileStatus,
    CRMRiskProfile,
    CRMSubscription,
    CRMSubscriptionStatus,
    CRMTariffPlan,
    CRMTariffStatus,
    CRMBillingMode,
    CRMBillingPeriod,
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


def test_decision_context_includes_profiles_and_flags(session):
    client = CRMClient(
        id="client-1",
        tenant_id=1,
        legal_name="Client",
        country="RU",
        timezone="Europe/Moscow",
        status=CRMClientStatus.ACTIVE,
    )
    risk_profile = CRMRiskProfile(
        tenant_id=1,
        name="Risk",
        status=CRMProfileStatus.ACTIVE,
        risk_policy_id="policy-1",
        shadow_enabled=False,
    )
    limit_profile = CRMLimitProfile(
        tenant_id=1,
        name="Limits",
        status=CRMProfileStatus.ACTIVE,
        definition={"limits": []},
    )
    contract = CRMContract(
        tenant_id=1,
        client_id=client.id,
        contract_number="CNT-1",
        status=CRMContractStatus.ACTIVE,
        billing_mode=CRMBillingMode.POSTPAID,
        currency="RUB",
        risk_profile_id=risk_profile.id,
        limit_profile_id=limit_profile.id,
    )
    tariff = CRMTariffPlan(
        id="tariff-1",
        name="Tariff",
        status=CRMTariffStatus.ACTIVE,
        billing_period=CRMBillingPeriod.MONTHLY,
        base_fee_minor=0,
        currency="RUB",
    )
    subscription = CRMSubscription(
        tenant_id=1,
        client_id=client.id,
        tariff_plan_id=tariff.id,
        status=CRMSubscriptionStatus.ACTIVE,
        billing_cycle=CRMBillingCycle.MONTHLY,
        billing_day=1,
        started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    flag = CRMFeatureFlag(
        tenant_id=1,
        client_id=client.id,
        feature=CRMFeatureFlagType.RISK_BLOCKING_ENABLED,
        enabled=True,
    )
    session.add_all([client, risk_profile, limit_profile, contract, tariff, subscription, flag])
    session.commit()

    payload = build_decision_context(session, tenant_id=1, client_id=client.id)

    assert payload["active_contract"].id == contract.id
    assert payload["tariff"].id == tariff.id
    assert payload["risk_profile"].id == risk_profile.id
    assert payload["limit_profile"].id == limit_profile.id
    assert payload["enforcement_flags"]["risk_blocking_enabled"] is True
