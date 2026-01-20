from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine, get_db
from app.main import app
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.partner import Partner
from app.models.terminal import Terminal
from app.services import transactions_service


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _override_db_dependency():
    def _get_db_override():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db_override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def seed_refs():
    db = SessionLocal()
    partner = Partner(
        id="partner-1",
        name="Test Partner",
        type="AZS",
        status="active",
        allowed_ips=["testclient"],
        token="token-123",
    )
    client_id = uuid4()
    db.add(partner)
    db.add(Client(id=client_id, name="Client", status="ACTIVE"))
    db.add(Card(id="card-1", client_id=str(client_id), status="ACTIVE"))
    db.add(Merchant(id="m-1", name="M1", status="ACTIVE"))
    db.add(Terminal(id="t-1", merchant_id="m-1", status="ACTIVE"))
    db.commit()
    db.close()
    return {"partner": partner, "card_id": "card-1", "terminal_id": "t-1"}


def _intake_payload(seed_refs: dict, **overrides):
    payload = {
        "external_partner_id": seed_refs["partner"].id,
        "terminal_id": seed_refs["terminal_id"],
        "amount": 10_000,
        "currency": "RUB",
        "card_identifier": seed_refs["card_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "product_id": "fuel-95",
        "liters": 20.5,
    }
    payload.update(overrides)
    return payload


def _auth_headers(seed_refs: dict):
    return {"x-partner-token": seed_refs["partner"].token}


def test_intake_authorize_success(client: TestClient, seed_refs: dict, monkeypatch: pytest.MonkeyPatch):
    def allow_risk(context, db=None):
        return transactions_service.risk_adapter.RiskEvaluation(
            decision=transactions_service.risk_adapter.RiskDecision(
                level=transactions_service.risk_adapter.RiskDecisionLevel.LOW,
                rules_fired=[],
                reason_codes=[],
            ),
            score=0.1,
            source="test",
            flags={},
        )

    monkeypatch.setattr(transactions_service, "RISK_ENGINE_OVERRIDE", allow_risk)
    response = client.post("/api/v1/intake/authorize", json=_intake_payload(seed_refs), headers=_auth_headers(seed_refs))
    data = response.json()
    assert response.status_code == 200
    assert data["approved"] is True
    assert data["posting_status"] == "POSTED"
    assert data["operation_id"]


def test_intake_risk_decline(client: TestClient, seed_refs: dict, monkeypatch: pytest.MonkeyPatch):
    def hard_decline(context, db=None):
        return transactions_service.risk_adapter.RiskEvaluation(
            decision=transactions_service.risk_adapter.RiskDecision(
                level=transactions_service.risk_adapter.RiskDecisionLevel.HARD_DECLINE,
                rules_fired=["hard"],
                reason_codes=["block"],
            ),
            score=1.0,
            source="test",
            flags={},
        )

    monkeypatch.setattr(transactions_service, "RISK_ENGINE_OVERRIDE", hard_decline)
    response = client.post("/api/v1/intake/authorize", json=_intake_payload(seed_refs), headers=_auth_headers(seed_refs))
    data = response.json()
    assert response.status_code == 200
    assert data["approved"] is False
    assert data["posting_status"] == "DECLINED"
    assert data["risk_code"] in {"BLOCK", "RISK_HARD_DECLINE"}


def test_intake_limit_decline(client: TestClient, seed_refs: dict):
    payload = _intake_payload(seed_refs, amount=200_000)
    response = client.post("/api/v1/intake/authorize", json=payload, headers=_auth_headers(seed_refs))
    data = response.json()
    assert response.status_code == 200
    assert data["approved"] is False
    assert data["posting_status"] == "DECLINED"
    assert data["limit_code"] == "LIMIT_EXCEEDED"


def test_intake_posting_error(client: TestClient, seed_refs: dict, monkeypatch: pytest.MonkeyPatch):
    def allow_risk(context, db=None):
        return transactions_service.risk_adapter.RiskEvaluation(
            decision=transactions_service.risk_adapter.RiskDecision(
                level=transactions_service.risk_adapter.RiskDecisionLevel.LOW,
                rules_fired=[],
                reason_codes=[],
            ),
            score=0.1,
            source="test",
            flags={},
        )

    monkeypatch.setattr(transactions_service, "RISK_ENGINE_OVERRIDE", allow_risk)
    payload = _intake_payload(seed_refs, simulate_posting_error=True)
    response = client.post("/api/v1/intake/authorize", json=payload, headers=_auth_headers(seed_refs))
    data = response.json()
    assert response.status_code == 200
    assert data["approved"] is False
    assert data["posting_status"] == "ERROR"
    assert data["response_code"] == "POSTING_ERROR"


def test_invalid_partner_rejected(client: TestClient, seed_refs: dict):
    payload = _intake_payload(seed_refs)
    headers = _auth_headers(seed_refs)
    headers["x-forwarded-for"] = "192.168.1.10"
    response = client.post("/api/v1/intake/authorize", json=payload, headers=headers)
    assert response.status_code == 403
