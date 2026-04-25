from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.card import Card
from app.models.card_access import CardAccess
from app.models.card_limits import CardLimit
from app.models.client import Client
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.models.client_operations import ClientOperation
from app.models.client_user_roles import ClientUserRole
from app.models.fuel import FleetOfflineProfile
from app.models.limit_templates import LimitTemplate
from app.routers import client_portal_v1
from app.services import client_auth
from app.tests._scoped_router_harness import scoped_session_context


@pytest.fixture()
def db_session() -> Session:
    tables = (
        FleetOfflineProfile.__table__,
        Client.__table__,
        Card.__table__,
        CardLimit.__table__,
        LimitTemplate.__table__,
        CardAccess.__table__,
        ClientOperation.__table__,
        ClientUserRole.__table__,
        ClientOnboardingContract.__table__,
        ClientOnboarding.__table__,
        AuditLog.__table__,
    )
    with scoped_session_context(tables=tables) as session:
        yield session


def _seed_client(session: Session, client_id: str) -> None:
    session.add(Client(id=UUID(client_id), name="Client Portal", status="ONBOARDING"))
    session.commit()


def _portal_token(client_id: str, *, sub: str, roles: list[str]) -> dict:
    return {
        "client_id": client_id,
        "sub": sub,
        "user_id": sub,
        "email": f"{sub}@neft.local",
        "role": roles[0],
        "roles": roles,
    }


@contextmanager
def _portal_client(db_session: Session, *, token: dict):
    app = FastAPI()
    app.include_router(client_portal_v1.router, prefix="/api/core")

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[client_auth.require_onboarding_user] = lambda: token

    original_enforce = client_portal_v1._enforce_portal_write_access
    client_portal_v1._enforce_portal_write_access = lambda **kwargs: None
    try:
        with TestClient(app) as api_client:
            yield api_client
    finally:
        client_portal_v1._enforce_portal_write_access = original_enforce


def test_cards_access_and_audit_flow(db_session: Session):
    client_id = str(uuid4())
    _seed_client(db_session, client_id)

    owner_token = _portal_token(client_id, sub="owner-1", roles=["CLIENT_OWNER"])
    with _portal_client(db_session, token=owner_token) as api_client:
        card_a_resp = api_client.post("/api/core/client/cards", json={"pan_masked": "1111"})
        assert card_a_resp.status_code == 201
        card_a = card_a_resp.json()

        card_b_resp = api_client.post("/api/core/client/cards", json={"pan_masked": "2222"})
        assert card_b_resp.status_code == 201
        card_b = card_b_resp.json()

        access_resp = api_client.post(
            f"/api/core/client/cards/{card_a['id']}/access",
            json={"user_id": "driver-1", "scope": "USE"},
        )
        assert access_resp.status_code == 200

        db_session.add(
            ClientOperation(
                id=1,
                client_id=UUID(client_id),
                card_id=card_a["id"],
                operation_type="PAYMENT",
                status="APPROVED",
                amount=100,
                currency="RUB",
            )
        )
        db_session.add(
            ClientOperation(
                id=2,
                client_id=UUID(client_id),
                card_id=card_b["id"],
                operation_type="PAYMENT",
                status="APPROVED",
                amount=200,
                currency="RUB",
            )
        )
        db_session.commit()

    driver_token = _portal_token(client_id, sub="driver-1", roles=["CLIENT_USER"])
    with _portal_client(db_session, token=driver_token) as driver_client:
        cards_resp = driver_client.get("/api/core/client/cards")
        assert cards_resp.status_code == 200
        cards = cards_resp.json()
        assert len(cards["items"]) == 1
        assert cards["items"][0]["id"] == card_a["id"]

        forbidden = driver_client.get(f"/api/core/client/cards/{card_b['id']}")
        assert forbidden.status_code == 403

        txs_resp = driver_client.get(f"/api/core/client/cards/{card_a['id']}/transactions")
        assert txs_resp.status_code == 200
        txs = txs_resp.json()
        assert len(txs) == 1
        assert txs[0]["card_id"] == card_a["id"]

        forbidden_tx = driver_client.get(f"/api/core/client/cards/{card_b['id']}/transactions")
        assert forbidden_tx.status_code == 403

    with _portal_client(db_session, token=owner_token) as api_client:
        block = api_client.patch(f"/api/core/client/cards/{card_a['id']}", json={"status": "BLOCKED"})
        assert block.status_code == 200

        limit = api_client.patch(
            f"/api/core/client/cards/{card_a['id']}/limits",
            json={"limit_type": "DAILY_AMOUNT", "amount": 5000, "currency": "RUB"},
        )
        assert limit.status_code == 200

        role_update = api_client.patch(
            "/api/core/client/users/driver-1/roles",
            json={"roles": ["CLIENT_MANAGER"]},
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

    with _portal_client(db_session, token=owner_token) as api_client:
        sign_resp = api_client.post("/api/core/client/contracts/sign-simple", json={"otp": "0000"})
        assert sign_resp.status_code == 200

    audit_events = {row[0] for row in db_session.query(AuditLog.event_type).all()}
    assert "card_block" in audit_events
    assert "limit_change" in audit_events
    assert "role_change" in audit_events
    assert "contract_sign" in audit_events
