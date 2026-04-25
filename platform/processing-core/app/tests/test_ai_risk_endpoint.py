from uuid import uuid4

import httpx
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints.transactions import router as transactions_router
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.operation import Operation, RiskResult
from app.models.risk_score import RiskLevel
from app.models.terminal import Terminal
from app.models.unified_rule import UnifiedRulePolicy
from app.services import risk_adapter, risk_rules, transactions_service
from app.services.decision import DecisionEngine, DecisionOutcome, DecisionResult
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


AI_RISK_TEST_TABLES = (
    Client.__table__,
    Card.__table__,
    Merchant.__table__,
    Terminal.__table__,
    Operation.__table__,
)


class _ApprovedLimits:
    approved = True
    daily_limit = None
    limit_per_tx = None
    used_today = None
    new_used_today = None
    applied_rule_id = "rule-ai"

    def model_dump(self):
        return {"approved": True, "applied_rule_id": self.applied_rule_id}


class _ApprovedContractualLimits:
    approved = True
    violations = []


class _DummyAsyncClient:
    def __init__(self, *args, **kwargs):
        self.request_url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        self.request_url = url
        return httpx.Response(
            200,
            json={
                "score": 0.42,
                "decision": "review",
                "reason": "manual check",
                "reasons": ["manual_check"],
                "model_version": "v-test",
            },
            request=httpx.Request("POST", url),
        )


def _allow_decision_result() -> DecisionResult:
    return DecisionResult(
        decision_id="decision-ai",
        decision_version="1",
        outcome=DecisionOutcome.ALLOW,
        risk_score=10,
        risk_level=RiskLevel.LOW,
        explain={},
    )


def _transactions_test_router() -> APIRouter:
    router = APIRouter()
    router.include_router(transactions_router)
    return router


@pytest.fixture
def db_session():
    with scoped_session_context(tables=AI_RISK_TEST_TABLES) as session:
        yield session


@pytest.fixture
def client(db_session: Session):
    with router_client_context(router=_transactions_test_router(), db_session=db_session) as api_client:
        yield api_client


def _seed_refs(db_session: Session) -> str:
    client_pk = uuid4()
    db_session.add(Client(id=client_pk, name="Client", status="ACTIVE"))
    db_session.add(Card(id="card-ai", client_id=str(client_pk), status="ACTIVE"))
    db_session.add(Merchant(id="merchant-ai", name="M", status="ACTIVE"))
    db_session.add(Terminal(id="terminal-ai", merchant_id="merchant-ai", status="ACTIVE"))
    db_session.commit()
    return str(client_pk)


def test_authorize_uses_ai_service(monkeypatch: pytest.MonkeyPatch, db_session: Session, client: TestClient):
    client_id = _seed_refs(db_session)
    dummy_client = _DummyAsyncClient()

    async def fake_rules(context, db=None, rules=None):
        return risk_adapter.RiskResult(risk_score=0.1, risk_result="LOW", reasons=[], flags={}, source="RULES")

    monkeypatch.setattr(risk_adapter.httpx, "AsyncClient", lambda *args, **kwargs: dummy_client)
    monkeypatch.setattr(risk_rules, "evaluate_rules", fake_rules)
    monkeypatch.setattr(risk_adapter.settings, "AI_RISK_ENABLED", True)
    monkeypatch.setattr(transactions_service, "evaluate_limits_locally", lambda *_, **__: _ApprovedLimits())
    monkeypatch.setattr(
        transactions_service,
        "check_contractual_limits",
        lambda *_, **__: _ApprovedContractualLimits(),
    )
    monkeypatch.setattr(transactions_service, "evaluate_with_db", lambda *_, **__: (UnifiedRulePolicy.ALLOW, [], None))
    monkeypatch.setattr(DecisionEngine, "evaluate", lambda *_args, **_kwargs: _allow_decision_result())
    monkeypatch.setattr(
        transactions_service,
        "_perform_posting",
        lambda *_, **__: {"accounts": [], "entries": []},
    )

    resp = client.post(
        "/api/v1/transactions/authorize",
        json={
            "client_id": client_id,
            "card_id": "card-ai",
            "terminal_id": "terminal-ai",
            "merchant_id": "merchant-ai",
            "amount": 1000,
            "currency": "RUB",
            "ext_operation_id": "ai-ext-1",
        },
    )

    assert resp.status_code == 200
    assert dummy_client.request_url.endswith("/api/v1/score/")

    db_session.expire_all()
    operation = db_session.query(Operation).filter(Operation.ext_operation_id == "ai-ext-1").one()

    assert operation.risk_result == RiskResult.MANUAL_REVIEW
    assert operation.risk_score == 0.42
    assert operation.risk_payload.get("source") == "AI"
    assert operation.risk_payload.get("decision", {}).get("ai_score") == 0.42
    assert operation.risk_payload.get("decision", {}).get("ai_model_version") == "v-test"
    assert "Unexpected status 307" not in str(operation.risk_payload)
    assert operation.risk_payload.get("flags", {}).get("ai_payload", {}).get("decision") == "review"
