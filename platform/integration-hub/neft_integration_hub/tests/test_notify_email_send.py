from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("neft_integration_hub")

import neft_integration_hub.main as main_module


def test_notify_email_send_mock_mode() -> None:
    object.__setattr__(main_module.settings, "app_env", "dev")
    object.__setattr__(main_module.settings, "email_provider_mode", "mock")
    with TestClient(main_module.app) as client:
        resp = client.post(
            "/api/int/notify/email/send",
            json={
                "to": "user@example.com",
                "subject": "Invite",
                "html": "<b>Hi</b>",
                "text": "Hi",
                "meta": {"template": "client_invite_v1"},
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"
    assert resp.json()["message_id"].startswith("mock:")


def test_notify_email_send_invalid_email() -> None:
    object.__setattr__(main_module.settings, "app_env", "dev")
    object.__setattr__(main_module.settings, "email_provider_mode", "mock")
    with TestClient(main_module.app) as client:
        resp = client.post(
            "/api/int/notify/email/send",
            json={"to": "invalid", "subject": "Invite", "html": "<b>Hi</b>", "text": "Hi"},
        )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_email"


def test_prod_mock_provider_returns_controlled_error(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    object.__setattr__(main_module.settings, "app_env", "prod")
    object.__setattr__(main_module.settings, "email_provider_mode", "mock")

    with TestClient(main_module.app) as client:
        resp = client.post(
            "/api/int/notify/email/send",
            json={"to": "user@example.com", "subject": "Invite", "text": "Hi"},
        )

    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "email_provider_not_configured"
