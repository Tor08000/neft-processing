from __future__ import annotations

import os
from typing import Any

import requests


def _build_url(path: str) -> str:
    base = os.getenv("GATEWAY_BASE_URL", "http://localhost").rstrip("/")
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{base}{normalized}"


def _assert_health(path: str, *, expected_service: str | None = None) -> None:
    response = requests.get(_build_url(path), timeout=5)
    assert response.status_code == 200

    payload: Any
    if "application/json" in response.headers.get("Content-Type", ""):
        payload = response.json()
        assert payload.get("status") == "ok"
        if expected_service:
            assert payload.get("service") == expected_service
    else:
        assert "OK" in response.text


def test_gateway_core_health_contract() -> None:
    _assert_health("/api/core/health")


def test_gateway_auth_health_contract() -> None:
    _assert_health("/api/auth/health", expected_service="auth-host")


def test_gateway_ai_health_contract() -> None:
    _assert_health("/api/ai/health", expected_service="ai-service")


def test_gateway_self_health_contract() -> None:
    _assert_health("/health")
