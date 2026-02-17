from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.audit_log import AuditLog
from app.models.card import Card
from app.models.client import Client
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.models.client_operations import ClientOperation


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_client(session, client_id: str) -> None:
    session.add(Client(id=client_id, name="Client Portal", status="ONBOARDING"))
    session.commit()


def test_cards_access_and_audit_flow(db_session, make_jwt):
    client_id = str(uuid4())
    _seed_client(db_session, client_id)

    owner_token = make_jwt(roles=("CLIENT_OWNER",), client_id=client_id, sub="owner-1")
    with TestClient(app, headers={"Authorization": f"Bearer {owner_token}"}) as api_client:
        card_a = api_client.post("/api/core/client/cards", json={"pan_masked": "1111"}).json()
        card_b = api_client.post("/api/core/client/cards", json={"pan_masked": "2222"}).json()

        access_resp = api_client.post(
            f"/api/core/client/cards/{card_a['id']}/access",
            json={"user_id": "driver-1", "scope": "USE"},
        )
        assert access_resp.status_code == 200

        db_session.add(
            ClientOperation(
                client_id=client_id,
                card_id=card_a["id"],
                operation_type="PAYMENT",
                status="APPROVED",
                amount=100,
                currency="RUB",
            )
        )
        db_session.add(
            ClientOperation(
                client_id=client_id,
                card_id=card_b["id"],
                operation_type="PAYMENT",
                status="APPROVED",
                amount=200,
                currency="RUB",
            )
        )
        db_session.commit()

    driver_token = make_jwt(roles=("CLIENT_USER",), client_id=client_id, sub="driver-1")
    with TestClient(app, headers={"Authorization": f"Bearer {driver_token}"}) as driver_client:
        cards = driver_client.get("/api/core/client/cards").json()
        assert len(cards["items"]) == 1
        assert cards["items"][0]["id"] == card_a["id"]

        forbidden = driver_client.get(f"/api/core/client/cards/{card_b['id']}")
        assert forbidden.status_code == 403

        txs = driver_client.get(f"/api/core/client/cards/{card_a['id']}/transactions").json()
        assert len(txs) == 1
        assert txs[0]["card_id"] == card_a["id"]

        forbidden_tx = driver_client.get(f"/api/core/client/cards/{card_b['id']}/transactions")
        assert forbidden_tx.status_code == 403

    with TestClient(app, headers={"Authorization": f"Bearer {owner_token}"}) as api_client:
        block = api_client.patch(f"/api/core/client/cards/{card_a['id']}", json={"status": "BLOCKED"})
        assert block.status_code == 200
        limit = api_client.patch(
            f"/api/core/client/cards/{card_a['id']}/limits",
            json={"limit_type": "DAILY_AMOUNT", "amount": 5000, "currency": "RUB"},
        )
        assert limit.status_code == 200

        role_update = api_client.patch(
            "/api/core/client/users/driver-1/roles",
            json={"roles": ["DRIVER"]},
        )
        assert role_update.status_code == 200

    contract_id = str(uuid4())
    db_session.add(
        ClientOnboarding(
            client_id=client_id,
            owner_user_id="owner-1",
            step="CONTRACT",
            status="DRAFT",
        )
    )
    db_session.add(
        ClientOnboardingContract(
            id=contract_id,
            client_id=client_id,
            status="DRAFT",
            pdf_url="http://example.com/contract.pdf",
            version=1,
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    db_session.query(ClientOnboarding).filter(ClientOnboarding.client_id == client_id).update(
        {"contract_id": contract_id}
    )
    db_session.commit()

    with TestClient(app, headers={"Authorization": f"Bearer {owner_token}"}) as api_client:
        sign_resp = api_client.post("/api/core/client/contracts/sign-simple", json={"otp": "0000"})
        assert sign_resp.status_code == 200

    audit_events = {row[0] for row in db_session.query(AuditLog.event_type).all()}
    assert "card_block" in audit_events
    assert "limit_change" in audit_events
    assert "role_change" in audit_events
    assert "contract_sign" in audit_events
