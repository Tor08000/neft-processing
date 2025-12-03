from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routes import processing
from app.lib import core_api
from app.main import app


def _client() -> TestClient:
    return TestClient(app)


def test_terminal_auth_happy_path(monkeypatch):
    payload = {
        "merchant_id": "m-1",
        "terminal_id": "t-1",
        "client_id": "c-1",
        "card_id": "card-1",
        "amount": 100.5,
        "currency": "RUB",
    }

    async def fake_proxy(request_payload):
        assert request_payload.merchant_id == payload["merchant_id"]
        return {
            "operation_id": "op-auth-1",
            "status": "AUTHORIZED",
            "authorized": True,
            "response_code": "00",
            "limits": {"daily_limit": 10000},
        }

    monkeypatch.setattr(processing, "proxy_terminal_auth", fake_proxy)
    monkeypatch.setattr(core_api, "proxy_terminal_auth", fake_proxy)
    assert processing.proxy_terminal_auth is fake_proxy

    response = _client().post("/api/v1/processing/terminal-auth", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["operation_id"] == "op-auth-1"
    assert body["authorized"] is True
    assert body["response_code"] == "00"
    assert body["limits"]["daily_limit"] == 10000


def test_terminal_auth_error_path(monkeypatch):
    async def fake_proxy(_payload):
        raise HTTPException(status_code=402, detail="limit_exceeded")

    monkeypatch.setattr(processing, "proxy_terminal_auth", fake_proxy)
    monkeypatch.setattr(core_api, "proxy_terminal_auth", fake_proxy)
    assert processing.proxy_terminal_auth is fake_proxy

    response = _client().post(
        "/api/v1/processing/terminal-auth",
        json={
            "merchant_id": "m-2",
            "terminal_id": "t-2",
            "client_id": "c-2",
            "card_id": "card-2",
            "amount": 50,
            "currency": "RUB",
        },
    )

    assert response.status_code == 402
    assert response.json()["detail"] == "limit_exceeded"


def test_terminal_capture_success(monkeypatch):
    captured: dict = {}

    async def fake_capture(*, auth_operation_id: str, amount: int | None = None):
        captured["id"] = auth_operation_id
        captured["amount"] = amount
        return {"operation_id": "op-cap-1", "status": "CAPTURED"}

    monkeypatch.setattr(processing, "capture_operation_via_core_api", fake_capture)
    monkeypatch.setattr(core_api, "capture_operation_via_core_api", fake_capture)
    assert processing.capture_operation_via_core_api is fake_capture

    response = _client().post(
        "/api/v1/processing/terminal-capture",
        json={"auth_operation_id": "op-auth-22", "amount": 75.2},
    )

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "operation_id": "op-cap-1",
        "status": "CAPTURED",
        "approved": True,
        "response_code": "00",
        "response_message": "approved",
    }
    assert captured == {"id": "op-auth-22", "amount": 75}


def test_terminal_capture_error(monkeypatch):
    async def fake_capture(*, auth_operation_id: str, amount: int | None = None):
        assert auth_operation_id == "missing-op"
        assert amount is None
        raise HTTPException(status_code=404, detail="auth_operation_not_found")

    monkeypatch.setattr(processing, "capture_operation_via_core_api", fake_capture)
    monkeypatch.setattr(core_api, "capture_operation_via_core_api", fake_capture)
    assert processing.capture_operation_via_core_api is fake_capture

    response = _client().post(
        "/api/v1/processing/terminal-capture",
        json={"auth_operation_id": "missing-op"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "auth_operation_not_found"
