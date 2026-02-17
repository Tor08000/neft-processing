from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.client import Client
from app.models.limit_templates import LimitTemplate


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
    session.add(Client(id=client_id, name="Cards Client", status="ACTIVE"))
    session.commit()


def test_get_cards_empty_returns_200(db_session, make_jwt):
    client_id = str(uuid4())
    _seed_client(db_session, client_id)
    token = make_jwt(roles=("CLIENT_OWNER",), client_id=client_id)

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        response = api_client.get("/api/core/client/cards")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert isinstance(payload.get("templates"), list)


def test_create_card_and_get(db_session, make_jwt):
    client_id = str(uuid4())
    _seed_client(db_session, client_id)
    token = make_jwt(roles=("CLIENT_OWNER",), client_id=client_id)

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        created = api_client.post("/api/core/client/cards", json={"label": "**** 4321", "template_id": None})
        assert created.status_code == 201
        card_id = created.json()["id"]

        cards = api_client.get("/api/core/client/cards")
        assert cards.status_code == 200
        items = cards.json()["items"]
        assert any(item["id"] == card_id for item in items)


def test_put_limits_replace_all(db_session, make_jwt):
    client_id = str(uuid4())
    _seed_client(db_session, client_id)
    token = make_jwt(roles=("CLIENT_OWNER",), client_id=client_id)

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        created = api_client.post("/api/core/client/cards", json={"label": "**** 9876"})
        card_id = created.json()["id"]

        update = api_client.put(
            f"/api/core/client/cards/{card_id}/limits",
            json={
                "limits": [
                    {"limit_type": "DAILY", "amount": 10000, "currency": "RUB", "active": True},
                    {"limit_type": "MONTHLY", "amount": 50000, "currency": "RUB", "active": True},
                ]
            },
        )
        assert update.status_code == 200

        cards = api_client.get("/api/core/client/cards").json()
        card = next(item for item in cards["items"] if item["id"] == card_id)
        assert len(card["limits"]) == 2


def test_access_other_client_card_forbidden(db_session, make_jwt):
    client_a = str(uuid4())
    client_b = str(uuid4())
    _seed_client(db_session, client_a)
    _seed_client(db_session, client_b)
    token_a = make_jwt(roles=("CLIENT_OWNER",), client_id=client_a)
    token_b = make_jwt(roles=("CLIENT_OWNER",), client_id=client_b)

    with TestClient(app, headers={"Authorization": f"Bearer {token_a}"}) as api_client_a:
        created = api_client_a.post("/api/core/client/cards", json={"label": "A"})
        card_id = created.json()["id"]

    with TestClient(app, headers={"Authorization": f"Bearer {token_b}"}) as api_client_b:
        update = api_client_b.put(
            f"/api/core/client/cards/{card_id}/limits",
            json={"limits": [{"limit_type": "DAILY", "amount": 1000, "currency": "RUB", "active": True}]},
        )

    assert update.status_code in {403, 404}


def test_create_card_uses_default_template(db_session, make_jwt):
    client_id = str(uuid4())
    _seed_client(db_session, client_id)
    db_session.add(
        LimitTemplate(
            client_id=client_id,
            name="Стандарт",
            description="default",
            limits=[{"type": "DAILY", "value": 5000, "currency": "RUB", "active": True}],
            is_default=True,
            status="ACTIVE",
        )
    )
    db_session.commit()

    token = make_jwt(roles=("CLIENT_OWNER",), client_id=client_id)
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        created = api_client.post("/api/core/client/cards", json={"label": "from template"})

    assert created.status_code == 201
    assert created.json()["limits"][0]["limit_type"] == "DAILY"
