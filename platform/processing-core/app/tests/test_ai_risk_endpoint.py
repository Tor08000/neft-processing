from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.operation import Operation, RiskResult
from app.models.terminal import Terminal
from app.services import risk_adapter, risk_rules


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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


def _seed_refs():
    client_pk = uuid4()
    db = SessionLocal()
    try:
        db.add(Client(id=client_pk, name="Client", status="ACTIVE"))
        db.add(Card(id="card-ai", client_id=str(client_pk), status="ACTIVE"))
        db.add(Merchant(id="merchant-ai", name="M", status="ACTIVE"))
        db.add(Terminal(id="terminal-ai", merchant_id="merchant-ai", status="ACTIVE"))
        db.commit()
    finally:
        db.close()
    return str(client_pk)


def test_authorize_uses_ai_service(monkeypatch):
    client_id = _seed_refs()
    dummy_client = _DummyAsyncClient()

    async def fake_rules(context, db=None, rules=None):
        return risk_adapter.RiskResult(risk_score=0.1, risk_result="LOW", reasons=[], flags={}, source="RULES")

    monkeypatch.setattr(risk_adapter.httpx, "AsyncClient", lambda *args, **kwargs: dummy_client)
    monkeypatch.setattr(risk_rules, "evaluate_rules", fake_rules)

    client = TestClient(app)
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

    db = SessionLocal()
    try:
        operation = db.query(Operation).filter(Operation.ext_operation_id == "ai-ext-1").one()
    finally:
        db.close()

    assert operation.risk_result == RiskResult.MANUAL_REVIEW
    assert operation.risk_score == 0.42
    assert operation.risk_payload.get("source") == "AI"
    assert operation.risk_payload.get("decision", {}).get("ai_score") == 0.42
    assert operation.risk_payload.get("decision", {}).get("ai_model_version") == "v-test"
    assert "Unexpected status 307" not in str(operation.risk_payload)
    assert operation.risk_payload.get("flags", {}).get("ai_payload", {}).get("decision") == "review"
