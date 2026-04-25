from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from neft_integration_hub import main
from neft_integration_hub.main import app


def test_otp_send_valid_and_idempotent() -> None:
    object.__setattr__(main.settings, "app_env", "dev")
    object.__setattr__(main.settings, "otp_provider_mode", "sandbox")
    with TestClient(app) as client:
        payload = {
            "channel": "sms",
            "destination": "+79990000000",
            "message": "code",
            "idempotency_key": "k1",
            "meta": {},
        }
        r1 = client.post("/api/int/v1/otp/send", json=payload)
        r2 = client.post("/api/int/v1/otp/send", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["provider_message_id"] == r2.json()["provider_message_id"]
        assert r1.json()["provider_message_id"].startswith("sandbox:")
        assert r1.json()["mode"] == "sandbox"


def test_otp_send_invalid_destination() -> None:
    object.__setattr__(main.settings, "app_env", "dev")
    with TestClient(app) as client:
        resp = client.post(
            "/api/int/v1/otp/send",
            json={"channel": "sms", "destination": "bad", "message": "code", "idempotency_key": "k2", "meta": {}},
        )
        assert resp.status_code == 422


def test_otp_send_degraded_mode_fails_explicitly() -> None:
    object.__setattr__(main.settings, "app_env", "dev")
    object.__setattr__(main.settings, "otp_provider_mode", "degraded")
    with TestClient(app) as client:
        resp = client.post(
            "/api/int/v1/otp/send",
            json={"channel": "sms", "destination": "+79990000000", "message": "code", "idempotency_key": "k3", "meta": {}},
        )
        assert resp.status_code == 503
        assert resp.json()["detail"]["category"] == "degraded"
        assert resp.json()["detail"]["error"] == "otp_provider_degraded"
