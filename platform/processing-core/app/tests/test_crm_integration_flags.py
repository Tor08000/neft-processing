from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.crm import CRMFeatureFlag, CRMFeatureFlagType
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelNetwork,
    FuelNetworkStatus,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
)
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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


def test_contract_pause_blocks_fuel_access(admin_auth_headers):
    client = TestClient(app)
    client.post(
        "/api/v1/admin/crm/clients",
        json={
            "id": "client-1",
            "tenant_id": 1,
            "legal_name": "Client",
            "country": "RU",
            "status": "ACTIVE",
        },
        headers=admin_auth_headers,
    )
    contract_resp = client.post(
        "/api/v1/admin/crm/clients/client-1/contracts",
        json={
            "tenant_id": 1,
            "contract_number": "CN-1",
            "status": "ACTIVE",
            "billing_mode": "POSTPAID",
            "currency": "RUB",
        },
        headers=admin_auth_headers,
    )
    contract_id = contract_resp.json()["id"]
    client.post(f"/api/v1/admin/crm/contracts/{contract_id}/pause", headers=admin_auth_headers)

    session = SessionLocal()
    try:
        _seed_fuel(session, client_id="client-1")
    finally:
        session.close()

    response = _authorize_fuel(client)
    assert response.status_code == 200
    assert response.json()["decline_code"] == "CLIENT_BLOCKED"


def test_risk_profile_applied_to_fuel_context(admin_auth_headers):
    client = TestClient(app)
    client.post(
        "/api/v1/admin/crm/clients",
        json={
            "id": "client-1",
            "tenant_id": 1,
            "legal_name": "Client",
            "country": "RU",
            "status": "ACTIVE",
        },
        headers=admin_auth_headers,
    )
    session = SessionLocal()
    try:
        threshold_set = RiskThresholdSet(
            id="payment-set",
            subject_type=RiskSubjectType.PAYMENT,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.PAYMENT,
            block_threshold=100,
            review_threshold=90,
            allow_threshold=0,
            valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        policy = RiskPolicy(
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
        session.add_all([threshold_set, policy])
        session.commit()
        _seed_fuel(session, client_id="client-1")
    finally:
        session.close()


def test_suspended_client_declines_fuel(admin_auth_headers):
    client = TestClient(app)
    client.post(
        "/api/v1/admin/crm/clients",
        json={
            "id": "client-1",
            "tenant_id": 1,
            "legal_name": "Client",
            "country": "RU",
            "status": "SUSPENDED",
        },
        headers=admin_auth_headers,
    )
    session = SessionLocal()
    try:
        _seed_fuel(session, client_id="client-1")
    finally:
        session.close()

    response = _authorize_fuel(client)
    assert response.status_code == 200
    assert response.json()["decline_code"] == "CLIENT_BLOCKED"


def test_enterprise_profile_review_requires_approval(admin_auth_headers):
    client = TestClient(app)
    client.post(
        "/api/v1/admin/crm/clients",
        json={
            "id": "client-1",
            "tenant_id": 1,
            "legal_name": "Client",
            "country": "RU",
            "status": "ACTIVE",
        },
        headers=admin_auth_headers,
    )
    session = SessionLocal()
    try:
        threshold_set = RiskThresholdSet(
            id="enterprise-review",
            subject_type=RiskSubjectType.PAYMENT,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.PAYMENT,
            block_threshold=100,
            review_threshold=50,
            allow_threshold=0,
            valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        policy = RiskPolicy(
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
        )
        session.add_all([threshold_set, policy])
        session.commit()
        _seed_fuel(session, client_id="client-1")
    finally:
        session.close()

    risk_profile_resp = client.post(
        "/api/v1/admin/crm/risk-profiles",
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
        headers=admin_auth_headers,
    )
    risk_profile_id = risk_profile_resp.json()["id"]
    contract_resp = client.post(
        "/api/v1/admin/crm/clients/client-1/contracts",
        json={
            "tenant_id": 1,
            "contract_number": "CN-1",
            "status": "DRAFT",
            "billing_mode": "POSTPAID",
            "currency": "RUB",
            "risk_profile_id": risk_profile_id,
        },
        headers=admin_auth_headers,
    )
    contract_id = contract_resp.json()["id"]
    client.post(f"/api/v1/admin/crm/contracts/{contract_id}/activate", headers=admin_auth_headers)

    response = _authorize_fuel(client)
    assert response.status_code == 200
    assert response.json()["status"] == "REVIEW"

    transaction_id = response.json()["transaction_id"]
    settle_response = client.post(f"/api/v1/fuel/transactions/{transaction_id}/settle")
    assert settle_response.status_code == 400
    assert settle_response.json()["detail"]["decline_code"] == "RISK_REVIEW_REQUIRED"

    risk_profile_resp = client.post(
        "/api/v1/admin/crm/risk-profiles",
        json={
            "tenant_id": 1,
            "name": "Risk",
            "status": "ACTIVE",
            "risk_policy_id": "CRM_POLICY",
            "threshold_set_id": "payment-set",
            "shadow_enabled": False,
        },
        headers=admin_auth_headers,
    )
    risk_profile_id = risk_profile_resp.json()["id"]
    contract_resp = client.post(
        "/api/v1/admin/crm/clients/client-1/contracts",
        json={
            "tenant_id": 1,
            "contract_number": "CN-1",
            "status": "DRAFT",
            "billing_mode": "POSTPAID",
            "currency": "RUB",
            "risk_profile_id": risk_profile_id,
        },
        headers=admin_auth_headers,
    )
    contract_id = contract_resp.json()["id"]
    client.post(f"/api/v1/admin/crm/contracts/{contract_id}/activate", headers=admin_auth_headers)

    response = _authorize_fuel(client)
    assert response.status_code == 200
    assert response.json()["status"] == "ALLOW"

    session = SessionLocal()
    try:
        tx = session.query(FuelTransaction).order_by(FuelTransaction.created_at.desc()).first()
        assert tx is not None
        policy_payload = tx.meta["risk_explain"]["policy"]
        assert policy_payload["policy_id"] == "CRM_POLICY"
        flag = (
            session.query(CRMFeatureFlag)
            .filter(CRMFeatureFlag.client_id == "client-1")
            .filter(CRMFeatureFlag.feature == CRMFeatureFlagType.RISK_BLOCKING_ENABLED)
            .one_or_none()
        )
        assert flag is not None
        assert flag.enabled is True
    finally:
        session.close()
