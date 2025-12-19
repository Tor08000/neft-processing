from __future__ import annotations

from tests.smoke.utils import http_get, read_json


def test_gateway_health():
    response = http_get("/health")
    body = response.read().decode()
    assert response.status == 200
    assert "OK" in body


def test_core_health_via_gateway():
    response = http_get("/api/core/health", expect_json=True)
    data = read_json(response)
    assert response.status == 200
    assert data.get("status") == "ok"


def test_admin_auth_health_via_gateway():
    response = http_get("/api/auth/health", expect_json=True)
    data = read_json(response)
    assert response.status == 200
    assert data.get("status") == "ok"
    assert data.get("service") == "auth-host"


def test_ai_health_via_gateway():
    response = http_get("/api/ai/health", expect_json=True)
    data = read_json(response)
    assert response.status == 200
    assert data.get("status") == "ok"
    assert data.get("service") == "ai-service"
