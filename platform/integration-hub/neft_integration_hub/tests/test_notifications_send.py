from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("neft_integration_hub")

import neft_integration_hub.main as main_module


def test_notifications_send_mock_mode(monkeypatch):
    object.__setattr__(main_module.settings, "notifications_mode", "mock")
    object.__setattr__(main_module.settings, "notifications_email_provider", "")

    with TestClient(main_module.app) as client:
        resp = client.post(
            "/api/int/v1/notifications/send",
            json={
                "channel": "email",
                "template": "client_invitation",
                "to": "user@example.com",
                "variables": {"accept_url": "https://example.com"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "mock"


def test_notifications_send_real_mode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    object.__setattr__(main_module.settings, "notifications_mode", "real")
    object.__setattr__(main_module.settings, "notifications_email_provider", "smtp")

    with TestClient(main_module.app) as client:
        resp = client.post(
            "/api/int/v1/notifications/send",
            json={
                "channel": "email",
                "template": "client_invitation",
                "to": "user@example.com",
                "variables": {"accept_url": "https://example.com"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "real"


def test_real_mode_without_provider_does_not_crash_startup(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    object.__setattr__(main_module.settings, "notifications_mode", "real")
    object.__setattr__(main_module.settings, "notifications_email_provider", "")
    object.__setattr__(main_module.settings, "email_provider_mode", "mock")
    object.__setattr__(main_module.settings, "app_env", "prod")

    main_module.startup()

    with TestClient(main_module.app) as client:
        health = client.get("/health")

    assert health.status_code == 200
    assert health.json()["email_provider"] == "disabled"
