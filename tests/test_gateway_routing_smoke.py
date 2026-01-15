from __future__ import annotations

import os
from typing import Any

import requests


DEFAULT_GATEWAY = "http://127.0.0.1"


def _build_url(path: str) -> str:
    base = os.getenv("GATEWAY_BASE_URL", DEFAULT_GATEWAY).rstrip("/")
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{base}{normalized}"


def _assert_head_ok(path: str) -> None:
    response = requests.head(_build_url(path), timeout=5)
    assert response.status_code == 200


def _assert_health(
    path: str,
    *,
    expected_service: str | None = None,
    require_json: bool = False,
) -> None:
    response = requests.get(_build_url(path), timeout=5)
    assert response.status_code == 200

    payload: Any
    if "application/json" in response.headers.get("Content-Type", ""):
        payload = response.json()
        assert payload.get("status") == "ok"
        if expected_service:
            assert payload.get("service") == expected_service
    else:
        if require_json:
            raise AssertionError("Expected JSON response.")
        assert "OK" in response.text


def test_gateway_core_health_contract() -> None:
    _assert_head_ok("/api/core/health")
    _assert_health("/api/core/health", require_json=True)


def test_gateway_auth_health_contract() -> None:
    _assert_health("/api/auth/health")


def test_gateway_ai_health_contract() -> None:
    _assert_health("/api/ai/api/v1/health")


def test_gateway_self_health_contract() -> None:
    _assert_health("/health")
