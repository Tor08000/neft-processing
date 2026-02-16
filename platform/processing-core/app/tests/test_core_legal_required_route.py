from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.security.rbac.principal import Principal, get_portal_principal


def _fake_db():
    class _DB:
        pass

    yield _DB()


def test_client_token_can_access_client_legal_required(monkeypatch):
    principal = Principal(
        user_id=None,
        roles={"client_user"},
        scopes=set(),
        client_id=None,
        partner_id=None,
        is_admin=False,
        raw_claims={"portal": "client", "client_id": "client-1", "user_id": "user-1", "sub": "user-1"},
    )

    app.dependency_overrides[get_portal_principal] = lambda: principal
    app.dependency_overrides[get_db] = _fake_db
    monkeypatch.setattr("app.routers.legal.settings.CORE_ONBOARDING_ENABLED", False)

    client = TestClient(app)
    response = client.get("/api/core/legal/required", headers={"Authorization": "Bearer test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["subject"]["type"] == "client"

    app.dependency_overrides.clear()
