from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.client import Client


def _seed_client() -> str:
    client_uuid = uuid4()
    client_id = str(client_uuid)
    session = SessionLocal()
    try:
        session.add(
            Client(
                id=client_uuid,
                name="Demo Client",
                email="client@neft.local",
                full_name="Client Demo",
                status="ACTIVE",
            )
        )
        session.commit()
    finally:
        session.close()
    return client_id


def test_client_v1_me_requires_token() -> None:
    with TestClient(app) as api_client:
        resp = api_client.get("/api/core/client/v1/me")
    assert resp.status_code == 401


def test_client_v1_me_returns_contract_shape(make_jwt) -> None:
    client_id = _seed_client()
    token = make_jwt(
        roles=("CLIENT_ADMIN",),
        client_id=client_id,
        sub="client-user-1",
        extra={"email": "client@neft.local", "full_name": "Client Demo", "tenant_id": 1},
    )

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        resp = api_client.get("/api/core/client/v1/me")

    assert resp.status_code == 200
    payload = resp.json()
    assert set(payload.keys()) == {"user", "client", "roles"}
    assert payload["user"]["id"] == "client-user-1"
    assert payload["user"]["email"] == "client@neft.local"
    assert payload["user"]["full_name"] == "Client Demo"
    assert payload["client"]["id"] == client_id
    assert payload["client"]["name"] == "Demo Client"
    assert "CLIENT_ADMIN" in payload["roles"]


def test_client_v1_router_is_registered() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/core/client/v1/me" in paths
    assert "/api/core/client/v1/health" in paths
