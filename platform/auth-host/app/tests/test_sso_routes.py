from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _client() -> TestClient:
    return TestClient(app)


def test_sso_idps_requires_tenant() -> None:
    response = _client().get("/api/v1/auth/sso/idps")
    assert response.status_code == 422
