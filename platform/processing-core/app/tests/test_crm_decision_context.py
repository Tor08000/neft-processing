from datetime import datetime, timezone

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
    CRMLimitProfile,
    CRMProfileStatus,
    CRMRiskProfile,
    CRMSubscription,
    CRMSubscriptionStatus,
    CRMTariffPlan,
    CRMTariffStatus,
)
from app.services.crm.decision_context import build_decision_context
from app.tests._crm_test_harness import crm_session_context


def test_decision_context_includes_profiles_and_flags():
    with crm_session_context() as session:
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
        session.add_all([client, risk_profile, limit_profile, tariff])
        session.commit()

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
        flag = CRMFeatureFlag(
            tenant_id=1,
            client_id=client.id,
            feature=CRMFeatureFlagType.RISK_BLOCKING_ENABLED,
            enabled=True,
        )
        session.add_all([contract, subscription, flag])
        session.commit()

        payload = build_decision_context(session, tenant_id=1, client_id=client.id)

        assert payload["active_contract"].id == contract.id
        assert payload["tariff"].id == tariff.id
        assert payload["risk_profile"].id == risk_profile.id
        assert payload["limit_profile"].id == limit_profile.id
        assert payload["enforcement_flags"]["risk_blocking_enabled"] is True
