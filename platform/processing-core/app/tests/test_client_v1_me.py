from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import FastAPI
from app.fastapi_utils import generate_unique_id

from app.db import get_db
from app.models.client import Client
from app.models.fuel import FleetOfflineProfile
from app.routers import client_v1
from app.security.client_auth import require_client_user
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def _seed_client(db_session, *, client_id: str) -> None:
    db_session.add(
        Client(
            id=UUID(client_id),
            name="Demo Client",
            email="client@neft.local",
            full_name="Client Demo",
            status="ACTIVE",
        )
    )
    db_session.commit()


def test_client_v1_me_requires_token() -> None:
    tables = (
        FleetOfflineProfile.__table__,
        Client.__table__,
    )
    with scoped_session_context(tables=tables) as db_session:
        with router_client_context(
            router=client_v1.router,
            prefix="/api/core",
            db_session=db_session,
        ) as api_client:
            resp = api_client.get("/api/core/client/v1/me")

    assert resp.status_code == 401


def test_client_v1_me_returns_contract_shape() -> None:
    client_id = str(uuid4())
    tables = (
        FleetOfflineProfile.__table__,
        Client.__table__,
    )
    with scoped_session_context(tables=tables) as db_session:
        _seed_client(db_session, client_id=client_id)
        token = {
            "sub": "client-user-1",
            "user_id": "client-user-1",
            "client_id": client_id,
            "email": "client@neft.local",
            "full_name": "Client Demo",
            "role": "CLIENT_ADMIN",
            "roles": ["CLIENT_ADMIN"],
            "tenant_id": 1,
        }
        with router_client_context(
            router=client_v1.router,
            prefix="/api/core",
            db_session=db_session,
            dependency_overrides={require_client_user: lambda: token},
        ) as api_client:
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
    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(client_v1.router, prefix="/api/core")

    paths = {route.path for route in app.routes}
    assert "/api/core/client/v1/me" in paths
    assert "/api/core/client/v1/health" in paths
