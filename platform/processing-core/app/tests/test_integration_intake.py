from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.intake import router as intake_router
from app.models.account import Account, AccountBalance
from app.models.card import Card
from app.models.client import Client
from app.models.external_request_log import ExternalRequestLog
from app.models.fuel import FuelNetwork, FuelStation, FuelStationNetwork
from app.models.ledger_entry import LedgerEntry
from app.models.limit_rule import LimitRule
from app.models.merchant import Merchant
from app.models.operation import Operation
from app.models.partner import Partner
from app.models.risk_score import RiskLevel
from app.models.terminal import Terminal
from app.models.unified_rule import UnifiedRulePolicy
from app.services import transactions_service
from app.services.decision import DecisionOutcome, DecisionResult
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


INTAKE_TEST_TABLES = (
    Partner.__table__,
    Client.__table__,
    Card.__table__,
    Merchant.__table__,
    Terminal.__table__,
    FuelNetwork.__table__,
    FuelStationNetwork.__table__,
    FuelStation.__table__,
    Operation.__table__,
    LimitRule.__table__,
    Account.__table__,
    AccountBalance.__table__,
    LedgerEntry.__table__,
    ExternalRequestLog.__table__,
)


class _ApprovedContractLimits:
    approved = True
    violations: list[object] = []


def _allow_decision() -> DecisionResult:
    return DecisionResult(
        decision_id=str(uuid4()),
        decision_version="test",
        outcome=DecisionOutcome.ALLOW,
        risk_score=0,
        risk_level=RiskLevel.LOW,
        explain={"reason_codes": []},
    )


@pytest.fixture(autouse=True)
def _allow_intake_dependencies(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(transactions_service, "RISK_ENGINE_OVERRIDE", None)
    monkeypatch.setattr(
        transactions_service.DecisionEngine,
        "evaluate",
        lambda *_args, **_kwargs: _allow_decision(),
    )
    monkeypatch.setattr(
        transactions_service,
        "evaluate_with_db",
        lambda *_args, **_kwargs: (UnifiedRulePolicy.ALLOW, [], None),
    )
    monkeypatch.setattr(
        transactions_service,
        "check_contractual_limits",
        lambda *_args, **_kwargs: _ApprovedContractLimits(),
    )


@pytest.fixture
def session():
    with scoped_session_context(tables=INTAKE_TEST_TABLES) as session:
        yield session


@pytest.fixture
def client(session) -> TestClient:
    with router_client_context(router=intake_router, db_session=session) as client:
        yield client


@pytest.fixture
def seed_refs(session):
    partner_id = str(uuid4())
    client_id = uuid4()
    merchant_id = str(uuid4())
    fuel_network_id = str(uuid4())
    station_network_id = str(uuid4())
    station_id = str(uuid4())

    partner = Partner(
        id=partner_id,
        name="Test Partner",
        type="AZS",
        code="PARTNER-1",
        legal_name="Test Partner LLC",
        partner_type="OTHER",
        status="ACTIVE",
        allowed_ips=["testclient"],
        token="token-123",
        contacts={},
    )
    session.add(partner)
    session.add(Client(id=client_id, name="Client", status="ACTIVE"))
    session.add(Card(id="card-1", client_id=str(client_id), status="ACTIVE"))
    session.add(Merchant(id=merchant_id, name="M1", status="ACTIVE"))
    session.add(Terminal(id="t-1", merchant_id=merchant_id, status="ACTIVE"))
    session.add(
        FuelNetwork(
            id=fuel_network_id,
            name="Network",
            provider_code="network-1",
            status="ACTIVE",
        )
    )
    session.add(FuelStationNetwork(id=station_network_id, name="Station Network"))
    session.add(
        FuelStation(
            id=station_id,
            network_id=fuel_network_id,
            station_network_id=station_network_id,
            name="Station",
            station_code="station-1",
            status="ACTIVE",
        )
    )
    session.commit()
    return {"partner_id": partner_id, "token": partner.token, "card_id": "card-1", "terminal_id": "t-1"}


def _intake_payload(seed_refs: dict[str, str], **overrides):
    payload = {
        "external_partner_id": seed_refs["partner_id"],
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


def _auth_headers(seed_refs: dict[str, str]):
    return {"x-partner-token": seed_refs["token"]}


def test_intake_authorize_success(client: TestClient, seed_refs: dict[str, str], monkeypatch: pytest.MonkeyPatch):
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


def test_intake_risk_decline(client: TestClient, seed_refs: dict[str, str], monkeypatch: pytest.MonkeyPatch):
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


def test_intake_limit_decline(client: TestClient, seed_refs: dict[str, str]):
    payload = _intake_payload(seed_refs, amount=200_000)
    response = client.post("/api/v1/intake/authorize", json=payload, headers=_auth_headers(seed_refs))
    data = response.json()
    assert response.status_code == 200
    assert data["approved"] is False
    assert data["posting_status"] == "DECLINED"
    assert data["limit_code"] == "LIMIT_EXCEEDED"


def test_intake_posting_error(client: TestClient, seed_refs: dict[str, str], monkeypatch: pytest.MonkeyPatch):
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


def test_invalid_partner_rejected(client: TestClient, seed_refs: dict[str, str]):
    payload = _intake_payload(seed_refs)
    headers = _auth_headers(seed_refs)
    headers["x-forwarded-for"] = "192.168.1.10"
    response = client.post("/api/v1/intake/authorize", json=payload, headers=headers)
    assert response.status_code == 403
