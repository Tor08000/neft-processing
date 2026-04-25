import pytest
from datetime import datetime, timezone
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
        "app.routers.explain_v2.build_explain_for_kpi",
        lambda **_: {
            "kind": "kpi",
            "id": "declines_total",
            "decision": "REVIEW",
            "generated_at": datetime.now(timezone.utc),
            "reason_tree": {"id": "declines_total", "title": "Declines", "weight": 1.0, "children": []},
            "evidence": [],
            "documents": [],
            "recommended_actions": [],
        },
    )


def test_explain_v2_kpi_success(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42, "aud": "neft-client"})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/explain",
            headers=_auth_headers(token),
            params={"kpi_key": "declines_total", "window_days": 7},
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["kind"] == "kpi"
    assert payload["id"] == "declines_total"
    assert payload["decision"] in {"APPROVE", "DECLINE", "REVIEW"}
    assert payload["reason_tree"]["weight"] == 1.0
    assert isinstance(payload["evidence"], list)


def test_explain_v2_kind_validation(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42, "aud": "neft-client"})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/explain",
            headers=_auth_headers(token),
            params={"kind": "unknown", "id": "op-1"},
        )

    assert resp.status_code == 422


def test_explain_v2_window_days_validation(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42, "aud": "neft-client"})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/explain",
            headers=_auth_headers(token),
            params={"kpi_key": "declines_total", "window_days": 5},
        )

    assert resp.status_code == 422


def test_explain_v2_client_tenant_override_forbidden(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42, "aud": "neft-client"})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/explain",
            headers=_auth_headers(token),
            params={"kpi_key": "declines_total", "window_days": 7, "tenant_id": 1},
        )

    assert resp.status_code == 403


def test_explain_v2_accepts_uuid_like_client_tenant_claim(make_jwt):
    token = make_jwt(
        roles=("CLIENT_USER",),
        client_id="client-1",
        extra={"tenant_id": "aaf19bab-c7ac-4cbf-9ad3-1d515fc6fb2c", "aud": "neft-client"},
    )

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/explain",
            headers=_auth_headers(token),
            params={"kpi_key": "declines_total", "window_days": 7},
        )

    assert resp.status_code == 200
