from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

pytest.importorskip("neft_integration_hub")

import neft_integration_hub.main as main_module


def test_notify_email_send_mock_mode() -> None:
    object.__setattr__(main_module.settings, "app_env", "dev")
    object.__setattr__(main_module.settings, "email_provider_mode", "sandbox")
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
    assert resp.json()["message_id"].startswith("sandbox:")
    assert resp.json()["mode"] == "sandbox"


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


def test_prod_mock_provider_is_blocked_by_guardrail(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    object.__setattr__(main_module.settings, "app_env", "prod")
    object.__setattr__(main_module.settings, "email_provider_mode", "mock")

    with pytest.raises(RuntimeError, match="prod guardrail violation"):
        with TestClient(main_module.app):
            pass


def test_disabled_email_provider_returns_degraded_error() -> None:
    object.__setattr__(main_module.settings, "app_env", "dev")
    object.__setattr__(main_module.settings, "email_provider_mode", "disabled")
    main_module.app.state.email_provider_enabled = False

    with TestClient(main_module.app) as client:
        resp = client.post(
            "/api/int/notify/email/send",
            json={"to": "user@example.com", "subject": "Invite", "text": "Hi"},
        )

    assert resp.status_code == 503
    assert resp.json()["detail"]["category"] == "degraded"
    assert resp.json()["detail"]["error"] == "email_provider_not_configured"
