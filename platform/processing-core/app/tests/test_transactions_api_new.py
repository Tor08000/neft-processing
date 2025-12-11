import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.terminal import Terminal


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_refs():
    client_pk = uuid4()
    db = SessionLocal()
    try:
        db.add(Client(id=client_pk, name="Client", status="ACTIVE"))
        db.add(Card(id="card-a", client_id=str(client_pk), status="ACTIVE"))
        db.add(Merchant(id="merchant-a", name="M", status="ACTIVE"))
        db.add(Terminal(id="terminal-a", merchant_id="merchant-a", status="ACTIVE"))
        db.commit()
        return str(client_pk)
    finally:
        db.close()


def test_authorize_endpoint_success():
    client_id = _seed_refs()
    client = TestClient(app)
    payload = {
        "client_id": client_id,
        "card_id": "card-a",
        "terminal_id": "terminal-a",
        "merchant_id": "merchant-a",
        "amount": 1000,
        "currency": "RUB",
        "ext_operation_id": "ext-api-1",
    }

    resp = client.post("/api/v1/transactions/authorize", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["approved"] is True
    assert data["status"] in {"AUTHORIZED", "POSTED"}
    assert data["operation_id"] == "ext-api-1"


def test_authorize_idempotent():
    client_id = _seed_refs()
    client = TestClient(app)
    payload = {
        "client_id": client_id,
        "card_id": "card-a",
        "terminal_id": "terminal-a",
        "merchant_id": "merchant-a",
        "amount": 1000,
        "currency": "RUB",
        "ext_operation_id": "ext-api-2",
    }
    first = client.post("/api/v1/transactions/authorize", json=payload)
    second = client.post("/api/v1/transactions/authorize", json=payload)

    assert first.json()["operation_id"] == second.json()["operation_id"]


def test_commit_and_refund_endpoints():
    client_id = _seed_refs()
    client = TestClient(app)
    auth_resp = client.post(
        "/api/v1/transactions/authorize",
        json={
            "client_id": client_id,
            "card_id": "card-a",
            "terminal_id": "terminal-a",
            "merchant_id": "merchant-a",
            "amount": 5000,
            "currency": "RUB",
            "ext_operation_id": "ext-api-3",
        },
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

