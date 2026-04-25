from app.models.crm import CRMFeatureFlag, CRMFeatureFlagType
from app.models.fuel import FuelCard, FuelCardStatus, FuelLimit
from app.tests._crm_test_harness import (
    CRM_CONTRACT_INTEGRATION_TEST_TABLES,
    CRM_TEST_HEADERS,
    crm_admin_client_context,
    crm_session_context,
)


def test_contract_activate_applies_limits_and_flags():
    with crm_session_context(tables=CRM_CONTRACT_INTEGRATION_TEST_TABLES) as session:
        with crm_admin_client_context(db_session=session) as client:
            client.post(
                "/api/core/v1/admin/crm/clients",
                json={
                    "id": "client-1",
                    "tenant_id": 1,
                    "legal_name": "Client",
                    "country": "RU",
                    "status": "ACTIVE",
                },
                headers=CRM_TEST_HEADERS,
            )
            limit_profile = client.post(
                "/api/core/v1/admin/crm/limit-profiles",
                json={
                    "tenant_id": 1,
                    "name": "Fuel Limits",
                    "status": "ACTIVE",
                    "definition": {
                        "version": 1,
                        "rules": [
                            {
                                "scope_type": "CLIENT",
                                "scope_selector": {"mode": "CLIENT_ALL", "filter": {}},
                                "limit_type": "AMOUNT",
                                "period": "DAILY",
                                "value": 100000,
                                "currency": "RUB",
                                "priority": 100,
                                "constraints": {
                                    "fuel_type": None,
                                    "station_id": None,
                                    "network_id": None,
                                    "time_window_start": None,
                                    "time_window_end": None,
                                    "timezone": "Europe/Moscow",
                                },
                                "meta": {"name": "Client daily cap", "purpose": "Test"},
                            }
                        ],
                    },
                },
                headers=CRM_TEST_HEADERS,
            )
            limit_profile_id = limit_profile.json()["id"]
            contract_resp = client.post(
                "/api/core/v1/admin/crm/clients/client-1/contracts",
                json={
                    "tenant_id": 1,
                    "contract_number": "CN-1",
                    "status": "DRAFT",
                    "billing_mode": "POSTPAID",
                    "currency": "RUB",
                    "limit_profile_id": limit_profile_id,
                },
                headers=CRM_TEST_HEADERS,
            )
            contract_id = contract_resp.json()["id"]
            activate_resp = client.post(
                f"/api/core/v1/admin/crm/contracts/{contract_id}/activate",
                headers=CRM_TEST_HEADERS,
            )
            assert activate_resp.status_code == 200

        assert session.query(FuelLimit).filter(FuelLimit.client_id == "client-1").count() == 1
        flag = (
            session.query(CRMFeatureFlag)
            .filter(CRMFeatureFlag.client_id == "client-1")
            .filter(CRMFeatureFlag.feature == CRMFeatureFlagType.FUEL_ENABLED)
            .one_or_none()
        )
        assert flag is not None
        assert flag.enabled is True


def test_apply_fuel_basic_idempotent():
    with crm_session_context(tables=CRM_CONTRACT_INTEGRATION_TEST_TABLES) as session:
        with crm_admin_client_context(db_session=session) as client:
            client.post(
                "/api/core/v1/admin/crm/clients",
                json={
                    "id": "client-1",
                    "tenant_id": 1,
                    "legal_name": "Client",
                    "country": "RU",
                    "status": "ACTIVE",
                },
                headers=CRM_TEST_HEADERS,
            )
            session.add(
                FuelCard(
                    tenant_id=1,
                    client_id="client-1",
                    card_token="card-1",
                    status=FuelCardStatus.ACTIVE,
                )
            )
            session.commit()

            limit_profile = client.post(
                "/api/core/v1/admin/crm/limit-profiles",
                json={
                    "tenant_id": 1,
                    "name": "FUEL_BASIC",
                    "status": "ACTIVE",
                    "definition": {
                        "version": 1,
                        "rules": [
                            {
                                "scope_type": "CLIENT",
                                "scope_selector": {"mode": "CLIENT_ALL", "filter": {}},
                                "limit_type": "AMOUNT",
                                "period": "MONTHLY",
                                "value": 50000000,
                                "currency": "RUB",
                                "priority": 500,
                                "constraints": {
                                    "fuel_type": None,
                                    "station_id": None,
                                    "network_id": None,
                                    "time_window_start": None,
                                    "time_window_end": None,
                                    "timezone": "Europe/Moscow",
                                },
                                "meta": {"name": "Monthly client amount cap", "purpose": "Global spend cap"},
                            },
                            {
                                "scope_type": "CARD",
                                "scope_selector": {"mode": "EACH_CARD", "filter": {}},
                                "limit_type": "AMOUNT",
                                "period": "DAILY",
                                "value": 300000,
                                "currency": "RUB",
                                "priority": 100,
                                "constraints": {
                                    "fuel_type": None,
                                    "station_id": None,
                                    "network_id": None,
                                    "time_window_start": None,
                                    "time_window_end": None,
                                    "timezone": "Europe/Moscow",
                                },
                                "meta": {"name": "Daily card spend limit", "purpose": "Reduce fraud impact"},
                            },
                            {
                                "scope_type": "CARD",
                                "scope_selector": {"mode": "EACH_CARD", "filter": {}},
                                "limit_type": "VOLUME",
                                "period": "DAILY",
                                "value": 200000,
                                "currency": None,
                                "priority": 90,
                                "constraints": {
                                    "fuel_type": None,
                                    "station_id": None,
                                    "network_id": None,
                                    "time_window_start": None,
                                    "time_window_end": None,
                                    "timezone": "Europe/Moscow",
                                },
                                "meta": {"name": "Daily card liters limit", "purpose": "Cap liters/day (ml)"},
                            },
                            {
                                "scope_type": "CARD",
                                "scope_selector": {"mode": "EACH_CARD", "filter": {}},
                                "limit_type": "COUNT",
                                "period": "DAILY",
                                "value": 5,
                                "currency": None,
                                "priority": 80,
                                "constraints": {
                                    "fuel_type": None,
                                    "station_id": None,
                                    "network_id": None,
                                    "time_window_start": None,
                                    "time_window_end": None,
                                    "timezone": "Europe/Moscow",
                                },
                                "meta": {"name": "Daily fueling count limit", "purpose": "Stop rapid refuel pattern"},
                            },
                        ],
                    },
                },
                headers=CRM_TEST_HEADERS,
            )
            limit_profile_id = limit_profile.json()["id"]
            contract_resp = client.post(
                "/api/core/v1/admin/crm/clients/client-1/contracts",
                json={
                    "tenant_id": 1,
                    "contract_number": "CN-1",
                    "status": "DRAFT",
                    "billing_mode": "POSTPAID",
                    "currency": "RUB",
                    "limit_profile_id": limit_profile_id,
                },
                headers=CRM_TEST_HEADERS,
            )
            contract_id = contract_resp.json()["id"]

            apply_resp = client.post(
                f"/api/core/v1/admin/crm/contracts/{contract_id}/apply",
                headers=CRM_TEST_HEADERS,
            )
            assert apply_resp.status_code == 200
            apply_resp = client.post(
                f"/api/core/v1/admin/crm/contracts/{contract_id}/apply",
                headers=CRM_TEST_HEADERS,
            )
            assert apply_resp.status_code == 200

        limits = (
            session.query(FuelLimit)
            .filter(FuelLimit.client_id == "client-1")
            .filter(FuelLimit.active.is_(True))
            .all()
        )
        assert len(limits) == 4
