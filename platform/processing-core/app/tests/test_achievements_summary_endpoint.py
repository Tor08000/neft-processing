from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.main import app


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _allow_mock_provider_guardrail_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    monkeypatch.setattr(app_main.settings, "APP_ENV", "dev", raising=False)
    monkeypatch.setattr(
        "app.routers.achievements.build_achievements_summary",
        lambda *_, window_days=7, **__: {
            "window_days": window_days,
            "as_of": datetime.now(timezone.utc),
            "badges": [
                {
                    "key": "first_steps",
                    "title": "First steps",
                    "description": "Stubbed badge",
                    "status": "locked",
                    "progress": 0.0,
                    "how_to": "Complete one action",
                    "meta": {},
                }
            ],
            "streak": {
                "key": "activity",
                "title": "Activity",
                "current": 0,
                "target": 7,
                "history": [],
                "status": "locked",
                "how_to": "Come back tomorrow",
            },
        },
    )


def test_achievements_summary_client_success(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 7, "aud": "neft-client"})

    with TestClient(app) as client:
        resp = client.get("/api/core/achievements/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["window_days"] == 7
    assert "as_of" in payload
    assert isinstance(payload["badges"], list)
    assert payload["badges"]
    badge_keys = {"key", "title", "description", "status", "progress", "how_to", "meta"}
    assert badge_keys.issubset(payload["badges"][0].keys())
    streak_keys = {"key", "title", "current", "target", "history", "status", "how_to"}
    assert streak_keys.issubset(payload["streak"].keys())


def test_achievements_summary_window_days_validation(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 7, "aud": "neft-client"})

    with TestClient(app) as client:
        resp = client.get("/api/core/achievements/summary", headers=_auth_headers(token), params={"window_days": 5})

    assert resp.status_code == 422


def test_achievements_summary_admin_tenant_override(make_jwt):
    token = make_jwt(roles=("SUPERADMIN",), extra={"tenant_id": 1})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/achievements/summary",
            headers=_auth_headers(token),
            params={"tenant_id": 2},
        )

    assert resp.status_code == 200


def test_achievements_summary_client_tenant_override_forbidden(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 7, "aud": "neft-client"})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/achievements/summary",
            headers=_auth_headers(token),
            params={"tenant_id": 2},
        )

    assert resp.status_code == 403


def test_achievements_summary_accepts_uuid_like_client_tenant_claim(make_jwt):
    token = make_jwt(
        roles=("CLIENT_USER",),
        client_id="client-1",
        extra={"tenant_id": "aaf19bab-c7ac-4cbf-9ad3-1d515fc6fb2c", "aud": "neft-client"},
    )

    with TestClient(app) as client:
        resp = client.get("/api/core/achievements/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
