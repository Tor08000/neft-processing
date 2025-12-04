import asyncio
from uuid import uuid4

import httpx
import pytest

import app.services.transactions_service as transactions_service
from app.db import Base, SessionLocal, engine
from app.models.operation import OperationStatus, RiskResult
from app.services.risk_adapter import OperationContext, call_risk_engine
from app.services.transactions_service import authorize_operation


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DummyClient:
    def __init__(self, responses):
        self._responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        data = self._responses.pop(0)
        return DummyResponse(data[0], data[1])


class DummyResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.request = None

    def json(self):
        return self._payload


def test_call_risk_engine_success(monkeypatch):
    responses = [(200, {"score": 0.2, "decision": "allow", "reasons": ["ok"]})]
    monkeypatch.setattr(
        "app.services.risk_adapter.httpx.AsyncClient",
        lambda timeout=3.0: DummyClient(responses),
    )
    context = OperationContext(
        client_id="c1",
        card_id="card-1",
        terminal_id="t1",
        merchant_id="m1",
        amount=10_000,
        currency="RUB",
    )

    result, score, payload = asyncio.run(call_risk_engine(context))

    assert result == RiskResult.LOW
    assert score == 0.2
    assert payload["reasons"] == ["ok"]


def test_call_risk_engine_fallback(monkeypatch):
    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):  # pragma: no cover - exercised via adapter
            raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr("app.services.risk_adapter.httpx.AsyncClient", lambda timeout=3.0: FailingClient())

    context = OperationContext(
        client_id="c1",
        card_id="card-1",
        terminal_id="t1",
        merchant_id="m1",
        amount=250_000,
        currency="RUB",
    )

    result, score, payload = asyncio.run(call_risk_engine(context))

    assert result in {RiskResult.MEDIUM, RiskResult.HIGH}
    assert score == 0.5
    assert payload.get("fallback") is True


def test_risk_block_declines_operation(monkeypatch, session):
    from app.models.card import Card
    from app.models.client import Client
    from app.models.merchant import Merchant
    from app.models.terminal import Terminal

    client_pk = uuid4()
    session.add(Client(id=client_pk, name="Test", status="ACTIVE"))
    session.add(Card(id="card-1", client_id=str(client_pk), status="ACTIVE"))
    session.add(Merchant(id="m-1", name="M1", status="ACTIVE"))
    session.add(Terminal(id="t-1", merchant_id="m-1", status="ACTIVE"))
    session.commit()

    async def blocking_call(context):
        return RiskResult.BLOCK, 0.9, {"reason": "blacklist", "risk_result": "BLOCK"}

    from app import services

    async def block_post_score(payload):
        return {"risk_score": 0.95, "risk_result": "BLOCK", "reasons": ["blacklist"]}

    monkeypatch.setattr("app.services.risk_adapter._post_score", block_post_score)
    monkeypatch.setattr(
        transactions_service, "call_risk_engine_sync", lambda ctx: asyncio.run(blocking_call(ctx))
    )

    probe_ctx = transactions_service.OperationContext(
        client_id=str(client_pk),
        card_id="card-1",
        terminal_id="t-1",
        merchant_id="m-1",
        amount=10_000,
        currency="RUB",
    )
    result, _, payload = transactions_service._evaluate_risk(probe_ctx)
    assert result == RiskResult.BLOCK
    assert payload["risk_result"] == "BLOCK"

    op = authorize_operation(
        session,
        client_id=str(client_pk),
        card_id="card-1",
        terminal_id="t-1",
        merchant_id="m-1",
        product_id=None,
        product_type=None,
        amount=10_000,
        currency="RUB",
        ext_operation_id="ext-block",
    )

    assert op.status == OperationStatus.DECLINED
    assert op.response_code == "RISK_BLOCK"
    assert op.risk_result == RiskResult.BLOCK
    assert op.risk_payload.get("reason") == "blacklist"
    assert op.risk_payload.get("risk_result") == "BLOCK"
