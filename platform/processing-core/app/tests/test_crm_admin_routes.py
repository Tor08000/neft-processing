from datetime import datetime, timezone

from app.models.crm import (
    CRMBillingCycle,
    CRMBillingMode,
    CRMClient,
    CRMClientStatus,
    CRMContract,
    CRMContractStatus,
    CRMSubscription,
    CRMSubscriptionStatus,
    CRMTariffPlan,
    CRMTariffStatus,
)
from app.tests._crm_test_harness import (
    CRM_ONBOARDING_TEST_TABLES,
    CRM_TEST_HEADERS,
    crm_admin_client_context,
    crm_session_context,
)


def test_admin_crm_detail_routes_and_feature_inference():
    with crm_session_context() as session:
        client_record = CRMClient(
            id="client-1",
            tenant_id=7,
            legal_name="Client One",
            country="RU",
            timezone="Europe/Moscow",
            status=CRMClientStatus.ACTIVE,
        )
        tariff = CRMTariffPlan(
            id="tariff-1",
            name="Tariff",
            status=CRMTariffStatus.ACTIVE,
            billing_period="MONTHLY",
            base_fee_minor=1000,
            currency="RUB",
            features={"fuel": True},
        )
        contract = CRMContract(
            tenant_id=7,
            client_id=client_record.id,
            contract_number="CNT-1",
            status=CRMContractStatus.DRAFT,
            billing_mode=CRMBillingMode.POSTPAID,
            currency="RUB",
        )
        subscription = CRMSubscription(
            tenant_id=7,
            client_id=client_record.id,
            tariff_plan_id=tariff.id,
            status=CRMSubscriptionStatus.ACTIVE,
            billing_cycle=CRMBillingCycle.MONTHLY,
            billing_day=1,
            started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        session.add_all([client_record, tariff, contract, subscription])
        session.commit()

        with crm_admin_client_context(db_session=session) as client:
            client_list = client.get(
                "/api/core/v1/admin/crm/clients",
                params={"status": "ACTIVE", "search": "Client One"},
                headers=CRM_TEST_HEADERS,
            )
            assert client_list.status_code == 200
            assert [item["id"] for item in client_list.json()] == ["client-1"]

            contract_get = client.get(
                f"/api/core/v1/admin/crm/contracts/{contract.id}",
                headers=CRM_TEST_HEADERS,
            )
            assert contract_get.status_code == 200
            assert contract_get.json()["contract_number"] == "CNT-1"

            contract_patch = client.patch(
                f"/api/core/v1/admin/crm/contracts/{contract.id}",
                json={"billing_mode": "PREPAID", "currency": "USD"},
                headers=CRM_TEST_HEADERS,
            )
            assert contract_patch.status_code == 200
            assert contract_patch.json()["billing_mode"] == "PREPAID"
            assert contract_patch.json()["currency"] == "USD"

            tariff_get = client.get(
                f"/api/core/v1/admin/crm/tariffs/{tariff.id}",
                headers=CRM_TEST_HEADERS,
            )
            assert tariff_get.status_code == 200
            assert tariff_get.json()["id"] == "tariff-1"

            subscription_get = client.get(
                f"/api/core/v1/admin/crm/subscriptions/{subscription.id}",
                headers=CRM_TEST_HEADERS,
            )
            assert subscription_get.status_code == 200
            assert subscription_get.json()["billing_day"] == 1

            subscription_patch = client.patch(
                f"/api/core/v1/admin/crm/subscriptions/{subscription.id}",
                json={"billing_day": 5},
                headers=CRM_TEST_HEADERS,
            )
            assert subscription_patch.status_code == 200
            assert subscription_patch.json()["billing_day"] == 5

            enable_feature = client.post(
                "/api/core/v1/admin/crm/clients/client-1/features/FUEL_ENABLED/enable",
                headers=CRM_TEST_HEADERS,
            )
            assert enable_feature.status_code == 200
            assert enable_feature.json()["tenant_id"] == 7
            assert enable_feature.json()["enabled"] is True

            feature_list = client.get(
                "/api/core/v1/admin/crm/clients/client-1/features",
                headers=CRM_TEST_HEADERS,
            )
            assert feature_list.status_code == 200
            assert feature_list.json()[0]["feature"] == "FUEL_ENABLED"


def test_admin_crm_lead_qualify_and_onboarding_action_routes():
    with crm_session_context(tables=CRM_ONBOARDING_TEST_TABLES) as session:
        with crm_admin_client_context(db_session=session) as client:
            lead_response = client.post(
                "/api/core/v1/admin/crm/leads",
                json={
                    "tenant_id": 1,
                    "source": "inbound",
                    "company_name": "Smoke LLC",
                    "contact_name": "QA",
                    "email": "qa+crm-admin@example.com",
                },
                headers=CRM_TEST_HEADERS,
            )
            assert lead_response.status_code == 200
            lead_id = lead_response.json()["id"]

            qualify_response = client.post(
                f"/api/core/v1/admin/crm/leads/{lead_id}/qualify",
                json={
                    "client_id": "client-smoke-admin",
                    "tenant_id": 1,
                    "country": "RU",
                    "legal_name": "Smoke LLC",
                },
                headers=CRM_TEST_HEADERS,
            )
            assert qualify_response.status_code == 200
            assert qualify_response.json()["id"] == "client-smoke-admin"

            request_legal = client.post(
                "/api/core/v1/admin/crm/clients/client-smoke-admin/onboarding/actions/REQUEST_LEGAL",
                headers=CRM_TEST_HEADERS,
            )
            assert request_legal.status_code == 200
            assert request_legal.json()["is_blocked"] is False
            assert request_legal.json()["evidence"]["legal_accepted"] is True
