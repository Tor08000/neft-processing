from __future__ import annotations

from uuid import UUID, uuid4

import app.main as app_main
import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from app.models.client import Client
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.routers import client_portal_v1
from app.services import client_fetch, portal_me


@pytest.fixture(autouse=True)
def clean_db(monkeypatch: pytest.MonkeyPatch):
    tables = [
        Client.__table__,
        ClientOnboardingContract.__table__,
        ClientOnboarding.__table__,
    ]
    monkeypatch.setattr(client_fetch, "DB_SCHEMA", None, raising=False)
    monkeypatch.setattr(client_portal_v1, "DB_SCHEMA", None, raising=False)
    monkeypatch.setattr(portal_me, "DB_SCHEMA", None, raising=False)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "dev", raising=False)
    Base.metadata.drop_all(bind=engine, tables=tables)
    Base.metadata.create_all(bind=engine, tables=tables)
    yield
    Base.metadata.drop_all(bind=engine, tables=tables)


def test_client_me_returns_active_org_and_current_access_state(make_jwt):
    client_id = str(uuid4())
    with engine.begin() as conn:
        conn.execute(
            Client.__table__.insert().values(
                id=UUID(client_id),
                name="Test Client",
                inn="7700",
                status="ACTIVE",
            )
        )

    token = make_jwt(
        roles=("CLIENT_ADMIN",),
        client_id=client_id,
        extra={"aud": "neft-client", "subject_type": "client_user", "user_id": "user-1"},
    )
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        response = api_client.get("/api/core/client/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["actor_type"] == "client"
    assert payload["context"] == "client"
    assert payload["org_status"] == "ACTIVE"
    assert payload["org"]["id"] == client_id
    assert payload["org_roles"] == ["CLIENT"]
    assert set(payload["user_roles"]) >= {"CLIENT_ADMIN", "CLIENT_OWNER"}
    assert payload["entitlements_snapshot"]["org_id"] == client_id
    assert payload["access_state"] == "NEEDS_ONBOARDING"
    assert payload["access_reason"] == "profile_missing"


def test_client_me_handles_missing_org(make_jwt):
    token = make_jwt(
        roles=("CLIENT_USER",),
        extra={"aud": "neft-client", "subject_type": "client_user", "user_id": "user-1"},
    )
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        response = api_client.get("/api/core/client/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["actor_type"] == "client"
    assert payload["org"] is None
    assert payload["org_status"] is None
    assert payload["entitlements_snapshot"]["org_id"] is None
    assert payload["access_state"] == "NEEDS_ONBOARDING"
    assert payload["access_reason"] == "org_pending"
