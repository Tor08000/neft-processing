from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_runtime_summary_schema(make_jwt):
    token = make_jwt(roles=("ADMIN",))

    with TestClient(app) as client:
        resp = client.get("/api/core/v1/admin/runtime/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    payload = resp.json()
    for key in ("health", "queues", "violations", "events"):
        assert key in payload
    assert "ts" in payload
    assert "environment" in payload
    assert "read_only" in payload


def test_admin_runtime_summary_statuses_valid(make_jwt):
    token = make_jwt(roles=("ADMIN",))

    with TestClient(app) as client:
        resp = client.get("/api/core/v1/admin/runtime/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    payload = resp.json()
    allowed = {"UP", "DEGRADED", "DOWN"}
    assert set(payload["health"].values()).issubset(allowed)


def test_admin_runtime_summary_read_only_propagates(make_jwt, monkeypatch):
    token = make_jwt(roles=("ADMIN",))
    monkeypatch.setattr(settings, "ADMIN_READ_ONLY", True)

    with TestClient(app) as client:
        resp = client.get("/api/core/v1/admin/runtime/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["read_only"] is True


def test_admin_runtime_summary_legacy_redirect(make_jwt):
    token = make_jwt(roles=("ADMIN",))

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/admin/runtime/summary",
            headers=_auth_headers(token),
            allow_redirects=False,
        )

    assert resp.status_code == 308
    assert resp.headers["location"].endswith("/api/core/v1/admin/runtime/summary")
