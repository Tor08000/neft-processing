from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.models.crm import CRMFeatureFlag, CRMFeatureFlagType
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelNetwork,
    FuelNetworkStatus,
    FuelRiskProfile,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
)
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services.fuel import analytics, fraud, risk_context
from app.tests._crm_test_harness import (
    CRM_FUEL_INTEGRATION_TEST_TABLES,
    CRM_TEST_HEADERS,
    crm_admin_fuel_client_context,
    crm_session_context,
)


@pytest.fixture(autouse=True)
def _isolate_unrelated_fuel_enrichment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fraud, "evaluate_fraud_signals", lambda *args, **kwargs: [])
    monkeypatch.setattr(fraud, "summarize_fraud_signals", lambda *args, **kwargs: {})
    monkeypatch.setattr(fraud, "persist_fraud_signals", lambda *args, **kwargs: None)
    monkeypatch.setattr(fraud, "fraud_signals_payload", lambda candidates, limit=3: [])
    monkeypatch.setattr(
        analytics,
        "evaluate_transaction",
        lambda **kwargs: analytics.AnalyticsResult(
            anomaly_events=[],
            analytics_events=[],
            misuse_signals=[],
            station_outliers=[],
        ),
    )
    monkeypatch.setattr(analytics, "persist_results", lambda *args, **kwargs: None)
    monkeypatch.setattr(risk_context.logistics_repository, "list_recent_risk_signals", lambda *args, **kwargs: [])
    monkeypatch.setattr(risk_context.logistics_repository, "list_recent_deviation_events", lambda *args, **kwargs: [])
    monkeypatch.setattr(risk_context.logistics_repository, "get_active_route", lambda *args, **kwargs: None)
    monkeypatch.setattr(risk_context.logistics_repository, "get_latest_route_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(risk_context.logistics_repository, "list_navigator_explains", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        risk_context.fi_repository,
        "latest_scores_for_ids",
        lambda *args, **kwargs: {"driver": None, "station": None, "vehicle": None},
    )
    monkeypatch.setattr(risk_context.fi_repository, "get_latest_trend_snapshot", lambda *args, **kwargs: None)


def _seed_fuel(session, *, client_id: str):
    network = FuelNetwork(id=str(uuid4()), name="Net", provider_code="NET-1", status=FuelNetworkStatus.ACTIVE)
    station = FuelStation(
        network_id=network.id,
        station_network_id=None,
        station_code="ST-1",
        name="Station",
        country="RU",
        region="RU",
        city="Moscow",
        lat="0",
        lon="0",
        status=FuelStationStatus.ACTIVE,
    )
    card = FuelCard(
        tenant_id=1,
        client_id=client_id,
        card_token="card-1",
        status=FuelCardStatus.ACTIVE,
    )
    session.add_all([network, station, card])
    session.commit()
    return card, network, station


def _authorize_fuel(client: TestClient):
    return client.post(
        "/api/v1/fuel/transactions/authorize",
        json={
            "card_token": "card-1",
            "network_code": "NET-1",
            "station_code": "ST-1",
            "fuel_type": "DIESEL",
            "volume_liters": 10,
            "unit_price": 5000,
            "currency": "RUB",
        },
    )


def test_contract_pause_blocks_fuel_access():
    with crm_session_context(tables=CRM_FUEL_INTEGRATION_TEST_TABLES) as session:
        with crm_admin_fuel_client_context(db_session=session) as client:
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
            contract_resp = client.post(
                "/api/core/v1/admin/crm/clients/client-1/contracts",
                json={
                    "tenant_id": 1,
                    "contract_number": "CN-1",
                    "status": "ACTIVE",
                    "billing_mode": "POSTPAID",
                    "currency": "RUB",
                },
                headers=CRM_TEST_HEADERS,
            )
            contract_id = contract_resp.json()["id"]
            client.post(
                f"/api/core/v1/admin/crm/contracts/{contract_id}/pause",
                headers=CRM_TEST_HEADERS,
            )
            _seed_fuel(session, client_id="client-1")

            response = _authorize_fuel(client)
            assert response.status_code == 200
            assert response.json()["decline_code"] == "CLIENT_BLOCKED"


def test_risk_profile_applied_to_fuel_context():
    with crm_session_context(tables=CRM_FUEL_INTEGRATION_TEST_TABLES) as session:
        session.add(
            RiskThresholdSet(
                id="payment-set",
                subject_type=RiskSubjectType.PAYMENT,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.PAYMENT,
                block_threshold=100,
                review_threshold=90,
                allow_threshold=0,
                valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        )
        session.add(
            RiskPolicy(
                id="CRM_POLICY",
                subject_type=RiskSubjectType.PAYMENT,
                tenant_id=None,
                client_id=None,
                provider=None,
                currency=None,
                country=None,
                threshold_set_id="payment-set",
                model_selector="risk_v4",
                priority=10,
                active=True,
            )
        )
        session.commit()

        with crm_admin_fuel_client_context(db_session=session) as client:
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
            risk_profile_resp = client.post(
                "/api/core/v1/admin/crm/risk-profiles",
                json={
                    "tenant_id": 1,
                    "name": "Risk",
                    "status": "ACTIVE",
                    "risk_policy_id": "CRM_POLICY",
                    "threshold_set_id": "payment-set",
                    "shadow_enabled": False,
                    "definition": {
                        "version": 1,
                        "signal_inputs": {
                            "use_logistics_signals": True,
                            "logistics_signal_window_hours": 48,
                            "severity_multiplier": 1.2,
                        }
                    },
                },
                headers=CRM_TEST_HEADERS,
            )
            risk_profile_id = risk_profile_resp.json()["id"]
            contract_resp = client.post(
                "/api/core/v1/admin/crm/clients/client-1/contracts",
                json={
                    "tenant_id": 1,
                    "contract_number": "CN-1",
                    "status": "DRAFT",
                    "billing_mode": "POSTPAID",
                    "currency": "RUB",
                    "risk_profile_id": risk_profile_id,
                },
                headers=CRM_TEST_HEADERS,
            )
            contract_id = contract_resp.json()["id"]
            activate_resp = client.post(
                f"/api/core/v1/admin/crm/contracts/{contract_id}/activate",
                headers=CRM_TEST_HEADERS,
            )
            assert activate_resp.status_code == 200

        applied = session.query(FuelRiskProfile).filter(FuelRiskProfile.client_id == "client-1").one()
        assert applied.policy_id == "CRM_POLICY"
        assert applied.enabled is True
        assert applied.thresholds_override["signal_inputs"]["logistics_signal_window_hours"] == 48


def test_suspended_client_declines_fuel():
    with crm_session_context(tables=CRM_FUEL_INTEGRATION_TEST_TABLES) as session:
        with crm_admin_fuel_client_context(db_session=session) as client:
            client.post(
                "/api/core/v1/admin/crm/clients",
                json={
                    "id": "client-1",
                    "tenant_id": 1,
                    "legal_name": "Client",
                    "country": "RU",
                    "status": "SUSPENDED",
                },
                headers=CRM_TEST_HEADERS,
            )
            _seed_fuel(session, client_id="client-1")

            response = _authorize_fuel(client)
            assert response.status_code == 200
            assert response.json()["decline_code"] == "CLIENT_BLOCKED"


def test_enterprise_profile_review_requires_approval():
    with crm_session_context(tables=CRM_FUEL_INTEGRATION_TEST_TABLES) as session:
        session.add_all(
            [
                RiskThresholdSet(
                    id="enterprise-review",
                    subject_type=RiskSubjectType.PAYMENT,
                    scope=RiskThresholdScope.GLOBAL,
                    action=RiskThresholdAction.PAYMENT,
                    block_threshold=100,
                    review_threshold=50,
                    allow_threshold=0,
                    valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
                ),
                RiskPolicy(
                    id="ENTERPRISE_FUEL_V4",
                    subject_type=RiskSubjectType.PAYMENT,
                    tenant_id=None,
                    client_id=None,
                    provider=None,
                    currency=None,
                    country=None,
                    threshold_set_id="enterprise-review",
                    model_selector="risk_v4",
                    priority=10,
                    active=True,
                ),
                RiskThresholdSet(
                    id="payment-set",
                    subject_type=RiskSubjectType.PAYMENT,
                    scope=RiskThresholdScope.GLOBAL,
                    action=RiskThresholdAction.PAYMENT,
                    block_threshold=100,
                    review_threshold=90,
                    allow_threshold=0,
                    valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
                ),
                RiskPolicy(
                    id="CRM_POLICY",
                    subject_type=RiskSubjectType.PAYMENT,
                    tenant_id=None,
                    client_id=None,
                    provider=None,
                    currency=None,
                    country=None,
                    threshold_set_id="payment-set",
                    model_selector="risk_v4",
                    priority=10,
                    active=True,
                ),
            ]
        )
        session.commit()

        with crm_admin_fuel_client_context(db_session=session) as client:
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
            _seed_fuel(session, client_id="client-1")

            risk_profile_resp = client.post(
                "/api/core/v1/admin/crm/risk-profiles",
                json={
                    "tenant_id": 1,
                    "name": "Enterprise Fuel",
                    "status": "ACTIVE",
                    "risk_policy_id": "ENTERPRISE_FUEL_V4",
                    "threshold_set_id": "enterprise-review",
                    "shadow_enabled": True,
                    "definition": {
                        "version": 1,
                        "profile_id": "enterprise_fuel_v4",
                        "signal_inputs": {
                            "use_logistics_signals": True,
                            "use_fuel_analytics_signals": True,
                            "logistics_signal_window_hours": 72,
                            "severity_multiplier": 1.3,
                        },
                        "thresholds_hint": {"allow_max": 100, "review_max": 0, "block_min": 101},
                    },
                },
                headers=CRM_TEST_HEADERS,
            )
            risk_profile_id = risk_profile_resp.json()["id"]
            contract_resp = client.post(
                "/api/core/v1/admin/crm/clients/client-1/contracts",
                json={
                    "tenant_id": 1,
                    "contract_number": "CN-1",
                    "status": "DRAFT",
                    "billing_mode": "POSTPAID",
                    "currency": "RUB",
                    "risk_profile_id": risk_profile_id,
                },
                headers=CRM_TEST_HEADERS,
            )
            contract_id = contract_resp.json()["id"]
            client.post(
                f"/api/core/v1/admin/crm/contracts/{contract_id}/activate",
                headers=CRM_TEST_HEADERS,
            )

            response = _authorize_fuel(client)
            assert response.status_code == 200
            assert response.json()["status"] == "REVIEW"

            transaction_id = response.json()["transaction_id"]
            settle_response = client.post(f"/api/v1/fuel/transactions/{transaction_id}/settle")
            assert settle_response.status_code == 400
            assert settle_response.json()["detail"]["decline_code"] == "RISK_REVIEW_REQUIRED"

            risk_profile_resp = client.post(
                "/api/core/v1/admin/crm/risk-profiles",
                json={
                    "tenant_id": 1,
                    "name": "Risk",
                    "status": "ACTIVE",
                    "risk_policy_id": "CRM_POLICY",
                    "threshold_set_id": "payment-set",
                    "shadow_enabled": False,
                },
                headers=CRM_TEST_HEADERS,
            )
            risk_profile_id = risk_profile_resp.json()["id"]
            contract_resp = client.post(
                "/api/core/v1/admin/crm/clients/client-1/contracts",
                json={
                    "tenant_id": 1,
                    "contract_number": "CN-1",
                    "status": "DRAFT",
                    "billing_mode": "POSTPAID",
                    "currency": "RUB",
                    "risk_profile_id": risk_profile_id,
                },
                headers=CRM_TEST_HEADERS,
            )
            contract_id = contract_resp.json()["id"]
            client.post(
                f"/api/core/v1/admin/crm/contracts/{contract_id}/activate",
                headers=CRM_TEST_HEADERS,
            )

            response = _authorize_fuel(client)
            assert response.status_code == 200
            assert response.json()["status"] == "ALLOW"
            allow_transaction_id = response.json()["transaction_id"]

        tx = session.query(FuelTransaction).filter(FuelTransaction.id == allow_transaction_id).one_or_none()
        assert tx is not None
        risk_explain = tx.meta["risk_explain"]
        assert risk_explain["policy"] == "CRM_POLICY"
        assert risk_explain["payload"]["policy_id"] == "CRM_POLICY"
        flag = (
            session.query(CRMFeatureFlag)
            .filter(CRMFeatureFlag.client_id == "client-1")
            .filter(CRMFeatureFlag.feature == CRMFeatureFlagType.RISK_BLOCKING_ENABLED)
            .one_or_none()
        )
        assert flag is not None
        assert flag.enabled is True
