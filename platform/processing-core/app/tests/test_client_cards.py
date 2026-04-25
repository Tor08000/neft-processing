from contextlib import contextmanager
from uuid import UUID
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.card import Card
from app.models.card_limits import CardLimit
from app.models.client import Client
from app.models.limit_templates import LimitTemplate
from app.routers import client_portal_v1
from app.services import client_auth
from app.tests._scoped_router_harness import scoped_session_context


@pytest.fixture()
def db_session() -> Session:
    tables = (
        Client.__table__,
        Card.__table__,
        CardLimit.__table__,
        LimitTemplate.__table__,
        AuditLog.__table__,
    )
    with scoped_session_context(tables=tables) as session:
        yield session


def _seed_client(session: Session, client_id: str) -> None:
    session.add(Client(id=UUID(client_id), name="Cards Client", status="ACTIVE"))
    session.commit()


@contextmanager
def _client_context(db_session: Session, *, token: dict):
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


def _owner_token(client_id: str, *, sub: str = "owner-1") -> dict:
    return {
        "client_id": client_id,
        "sub": sub,
        "user_id": sub,
        "email": f"{sub}@neft.local",
        "role": "CLIENT_OWNER",
        "roles": ["CLIENT_OWNER"],
    }


def test_get_cards_empty_returns_200(db_session: Session):
    client_id = str(uuid4())
    _seed_client(db_session, client_id)

    with _client_context(db_session, token=_owner_token(client_id)) as api_client:
        response = api_client.get("/api/core/client/cards")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert isinstance(payload.get("templates"), list)


def test_create_card_and_get(db_session: Session):
    client_id = str(uuid4())
    _seed_client(db_session, client_id)

    with _client_context(db_session, token=_owner_token(client_id)) as api_client:
        created = api_client.post("/api/core/client/cards", json={"label": "**** 4321", "template_id": None})
        assert created.status_code == 201
        card_id = created.json()["id"]

        cards = api_client.get("/api/core/client/cards")
        assert cards.status_code == 200
        items = cards.json()["items"]
        assert any(item["id"] == card_id for item in items)


def test_put_limits_replace_all(db_session: Session):
    client_id = str(uuid4())
    _seed_client(db_session, client_id)

    with _client_context(db_session, token=_owner_token(client_id)) as api_client:
        created = api_client.post("/api/core/client/cards", json={"label": "**** 9876"})
        card_id = created.json()["id"]

        update = api_client.put(
            f"/api/core/client/cards/{card_id}/limits",
            json={
                "limits": [
                    {"limit_type": "DAILY", "amount": 10000, "currency": "RUB"},
                    {"limit_type": "MONTHLY", "amount": 50000, "currency": "RUB"},
                ]
            },
        )
        assert update.status_code == 200

        cards = api_client.get("/api/core/client/cards").json()
        card = next(item for item in cards["items"] if item["id"] == card_id)
        assert len(card["limits"]) == 2


def test_access_other_client_card_forbidden(db_session: Session):
    client_a = str(uuid4())
    client_b = str(uuid4())
    _seed_client(db_session, client_a)
    _seed_client(db_session, client_b)

    with _client_context(db_session, token=_owner_token(client_a, sub="owner-a")) as api_client_a:
        created = api_client_a.post("/api/core/client/cards", json={"label": "A"})
        card_id = created.json()["id"]

    with _client_context(db_session, token=_owner_token(client_b, sub="owner-b")) as api_client_b:
        update = api_client_b.put(
            f"/api/core/client/cards/{card_id}/limits",
            json={"limits": [{"limit_type": "DAILY", "amount": 1000, "currency": "RUB"}]},
        )

    assert update.status_code in {403, 404}


def test_create_card_uses_default_template(db_session: Session):
    client_id = str(uuid4())
    _seed_client(db_session, client_id)
    db_session.add(
        LimitTemplate(
            client_id=UUID(client_id),
            name="РЎС‚Р°РЅРґР°СЂС‚",
            description="default",
            limits=[{"type": "DAILY", "value": 5000, "currency": "RUB", "active": True}],
            is_default=True,
            status="ACTIVE",
        )
    )
    db_session.commit()

    with _client_context(db_session, token=_owner_token(client_id)) as api_client:
        created = api_client.post("/api/core/client/cards", json={"label": "from template"})

    assert created.status_code == 201
    assert created.json()["limits"][0]["limit_type"] == "DAILY"
