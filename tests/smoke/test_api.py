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


def test_auth_health_via_gateway():
    response = http_get("/api/auth/health", expect_json=True)
    data = read_json(response)
    assert response.status == 200
    assert data.get("status") == "ok"


def test_ai_health_via_gateway():
    response = http_get("/api/ai/v1/health", expect_json=True)
    data = read_json(response)
    assert response.status == 200
    assert data.get("status") == "ok"


def test_direct_service_health():
    core = http_get("http://127.0.0.1:8001/health", expect_json=True)
    auth = http_get("http://127.0.0.1:8002/health", expect_json=True)
    ai = http_get("http://127.0.0.1:8003/api/v1/health", expect_json=True)

    for response in (core, auth, ai):
        data = read_json(response)
        assert response.status == 200
        assert data.get("status") == "ok"
