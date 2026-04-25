from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table
from sqlalchemy.orm import Session

from app.api.v1.endpoints.transactions import router as transactions_router
from app.models.account import Account, AccountBalance
from app.models.audit_log import AuditLog
from app.models.card import Card
from app.models.client import Client
from app.models.ledger_entry import LedgerEntry
from app.models.merchant import Merchant
from app.models.operation import Operation, OperationStatus
from app.models.risk_score import RiskLevel
from app.models.terminal import Terminal
from app.models.unified_rule import UnifiedRulePolicy
from app.services import transactions_service
from app.services.decision import DecisionEngine, DecisionOutcome, DecisionResult
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


_TRANSACTIONS_TEST_METADATA = MetaData()

FLEET_OFFLINE_PROFILES_REFLECTED = Table(
    "fleet_offline_profiles",
    _TRANSACTIONS_TEST_METADATA,
    Column("id", String(36), primary_key=True),
)

FUEL_STATIONS_REFLECTED = Table(
    "fuel_stations",
    _TRANSACTIONS_TEST_METADATA,
    Column("id", String(64), primary_key=True),
)

TRANSACTIONS_API_TEST_TABLES = (
    FLEET_OFFLINE_PROFILES_REFLECTED,
    FUEL_STATIONS_REFLECTED,
    Client.__table__,
    Card.__table__,
    Merchant.__table__,
    Terminal.__table__,
    Operation.__table__,
    Account.__table__,
    AccountBalance.__table__,
    LedgerEntry.__table__,
    AuditLog.__table__,
)


class _ApprovedLimits:
    approved = True
    daily_limit = None
    limit_per_tx = None
    used_today = None
    new_used_today = None
    applied_rule_id = "rule-api"

    def model_dump(self):
        return {"approved": True, "applied_rule_id": self.applied_rule_id}


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
        explain={},
    )


def _allow_risk(*_args, **_kwargs):
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


def _transactions_test_router() -> APIRouter:
    router = APIRouter()
    router.include_router(transactions_router)
    return router


@pytest.fixture(autouse=True)
def _allow_transaction_dependencies(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(transactions_service, "RISK_ENGINE_OVERRIDE", _allow_risk)
    monkeypatch.setattr(DecisionEngine, "evaluate", lambda *_args, **_kwargs: _allow_decision())
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
    monkeypatch.setattr(
        transactions_service,
        "evaluate_limits_locally",
        lambda *_, **__: _ApprovedLimits(),
    )


@pytest.fixture
def db_session():
    with scoped_session_context(tables=TRANSACTIONS_API_TEST_TABLES) as session:
        yield session


@pytest.fixture
def client(db_session: Session):
    with router_client_context(router=_transactions_test_router(), db_session=db_session) as api_client:
        yield api_client


def _seed_refs(db_session: Session) -> dict[str, str]:
    client_id = uuid4()
    merchant_id = str(uuid4())
    terminal_id = str(uuid4())
    refs = {
        "client_id": str(client_id),
        "card_id": "card-a",
        "merchant_id": merchant_id,
        "terminal_id": terminal_id,
    }

    db_session.add(Client(id=client_id, name="Client", status="ACTIVE"))
    db_session.add(Card(id=refs["card_id"], client_id=refs["client_id"], status="ACTIVE"))
    db_session.add(Merchant(id=merchant_id, name="M", status="ACTIVE"))
    db_session.add(Terminal(id=terminal_id, merchant_id=merchant_id, status="ACTIVE"))
    db_session.commit()
    return refs


def _authorize_payload(refs: dict[str, str], *, ext_operation_id: str, amount: int = 1000) -> dict[str, object]:
    return {
        "client_id": refs["client_id"],
        "card_id": refs["card_id"],
        "terminal_id": refs["terminal_id"],
        "merchant_id": refs["merchant_id"],
        "amount": amount,
        "currency": "RUB",
        "ext_operation_id": ext_operation_id,
    }


def test_authorize_endpoint_success(client: TestClient, db_session: Session):
    refs = _seed_refs(db_session)
    payload = _authorize_payload(refs, ext_operation_id="ext-api-1")

    resp = client.post("/api/v1/transactions/authorize", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["approved"] is True
    assert data["status"] in {"AUTHORIZED", "POSTED"}
    assert data["operation_id"] == "ext-api-1"


def test_authorize_idempotent(client: TestClient, db_session: Session):
    refs = _seed_refs(db_session)
    payload = _authorize_payload(refs, ext_operation_id="ext-api-2")

    first = client.post("/api/v1/transactions/authorize", json=payload)
    second = client.post("/api/v1/transactions/authorize", json=payload)

    assert first.json()["operation_id"] == second.json()["operation_id"]


def test_authorize_persists_operation_record(client: TestClient, db_session: Session):
    refs = _seed_refs(db_session)
    payload = _authorize_payload(refs, ext_operation_id="ext-api-4", amount=2500)

    resp = client.post("/api/v1/transactions/authorize", json=payload)
    assert resp.status_code == 200

    operations = db_session.query(Operation).all()

    assert len(operations) == 1
    op = operations[0]
    assert op.client_id == refs["client_id"]
    assert op.card_id == refs["card_id"]
    assert op.terminal_id == refs["terminal_id"]
    assert op.merchant_id == refs["merchant_id"]
    assert op.ext_operation_id == "ext-api-4"
    assert op.status in {OperationStatus.AUTHORIZED, OperationStatus.POSTED}


def test_commit_and_refund_endpoints(client: TestClient, db_session: Session):
    refs = _seed_refs(db_session)
    auth_resp = client.post(
        "/api/v1/transactions/authorize",
        json=_authorize_payload(refs, ext_operation_id="ext-api-3", amount=5000),
    ).json()

    commit_resp = client.post(
        "/api/v1/transactions/commit",
        json={"operation_id": auth_resp["operation_id"], "amount": 3000},
    )
    assert commit_resp.status_code == 200
    assert commit_resp.json()["status"] == "COMPLETED"

    refund_resp = client.post(
        "/api/v1/transactions/refund",
        json={"operation_id": auth_resp["operation_id"], "amount": 1000},
    )
    assert refund_resp.status_code == 200
    assert refund_resp.json()["operation_type"] == "REFUND"


def test_reverse_completed_returns_detail(client: TestClient, db_session: Session):
    refs = _seed_refs(db_session)
    auth_resp = client.post(
        "/api/v1/transactions/authorize",
        json=_authorize_payload(refs, ext_operation_id="ext-api-reverse", amount=5000),
    ).json()

    commit_resp = client.post(
        "/api/v1/transactions/commit",
        json={"operation_id": auth_resp["operation_id"], "amount": 5000},
    )
    assert commit_resp.status_code == 200

    reverse_resp = client.post(
        "/api/v1/transactions/reverse",
        json={"operation_id": auth_resp["operation_id"], "reason": "ops"},
    )

    assert reverse_resp.status_code == 409
    detail = reverse_resp.json()["detail"]
    assert detail["code"] == "INVALID_STATE"
    assert "use REFUND" in detail["message"]
