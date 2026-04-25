from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import app.main as app_main
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from app.db import Base, engine
from app.main import app
from app.models.client import Client
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.routers import client_portal_v1
from app.services import client_fetch
from app.services import portal_me


def _client_jwt(secret: str, *, client_id: str) -> str:
    payload = {
        "sub": "user-1",
        "user_id": "user-1",
        "subject_type": "client_user",
        "portal": "client",
        "roles": ["CLIENT_OWNER"],
        "role": "CLIENT_OWNER",
        "client_id": client_id,
        "aud": "neft-client",
        "iss": "neft-auth",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(autouse=True)
def clean_db(monkeypatch: pytest.MonkeyPatch):
    tables = [
        Client.__table__,
        ClientOnboardingContract.__table__,
        ClientOnboarding.__table__,
    ]
    secret = "portal-me-secret"
    monkeypatch.setenv("CLIENT_PUBLIC_KEY", secret)
    monkeypatch.setenv("CLIENT_TOKEN_SECRET", secret)
    monkeypatch.setattr("app.services.client_auth.ALLOWED_ALGS", ["HS256"], raising=False)
    monkeypatch.setattr("app.services.client_auth.EXPECTED_ISSUER", "neft-auth", raising=False)
    monkeypatch.setattr("app.services.client_auth.EXPECTED_AUDIENCE", "neft-client", raising=False)
    monkeypatch.setattr(client_fetch, "DB_SCHEMA", None, raising=False)
    monkeypatch.setattr(client_portal_v1, "DB_SCHEMA", None, raising=False)
    monkeypatch.setattr(portal_me, "DB_SCHEMA", None, raising=False)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "dev", raising=False)
    Base.metadata.drop_all(bind=engine, tables=tables)
    Base.metadata.create_all(bind=engine, tables=tables)
    yield
    Base.metadata.drop_all(bind=engine, tables=tables)


def test_portal_me_returns_client_org_after_profile():
    client_id = str(uuid4())
    token = _client_jwt("portal-me-secret", client_id=client_id)

    with Session(bind=engine) as db:
        db.add(Client(id=UUID(client_id), name="Черновик", inn="0000000000", status="ONBOARDING"))
        db.commit()

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        response = api_client.post(
            "/api/core/client/onboarding/profile",
            json={"org_type": "LEGAL", "name": "ООО ТЕСТ", "inn": "7707083893"},
        )
        assert response.status_code == 200

        response = api_client.get("/api/core/portal/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["org"] is not None
    assert payload["org"]["name"] == "ООО ТЕСТ"
    assert payload["org"]["inn"] == "7707083893"
    assert payload["org"]["org_type"] == "LEGAL"
    assert payload["org_status"] == "ONBOARDING"
    assert payload["access_reason"] != "profile_missing"
