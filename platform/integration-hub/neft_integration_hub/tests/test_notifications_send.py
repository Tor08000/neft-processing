from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

pytest.importorskip("neft_integration_hub")

import neft_integration_hub.main as main_module


def test_notifications_send_mock_mode(monkeypatch):
    object.__setattr__(main_module.settings, "notifications_mode", "sandbox")
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
        assert resp.json()["mode"] == "sandbox"
        assert resp.json()["provider"] == "sandbox"
        assert resp.json()["provider_message_id"].startswith("sandbox:")


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
        assert resp.status_code == 503
        assert resp.json()["detail"]["category"] == "degraded"
        assert resp.json()["detail"]["error"] == "notifications_transport_not_implemented"


def test_real_mode_without_provider_does_not_crash_startup(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("INTEGRATION_HUB_AUTO_CREATE_SCHEMA", "true")
    object.__setattr__(main_module.settings, "diadok_mode", "real")
    object.__setattr__(main_module.settings, "otp_provider_mode", "degraded")
    object.__setattr__(main_module.settings, "notifications_mode", "real")
    object.__setattr__(main_module.settings, "notifications_email_provider", "")
    object.__setattr__(main_module.settings, "email_provider_mode", "disabled")
    object.__setattr__(main_module.settings, "app_env", "prod")

    main_module.startup()

    with TestClient(main_module.app) as client:
        health = client.get("/health")

    assert health.status_code == 200
    assert health.json()["email_provider"] == "disabled"
    assert health.json()["provider_modes"]["notifications"] == "real"
    assert health.json()["database"]["ready"] is True


def test_health_reports_schema_not_ready(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_schema_health",
        lambda: {
            "ready": False,
            "auto_create_schema": False,
            "missing_tables": ["webhook_endpoints", "webhook_deliveries"],
            "error": None,
        },
    )

    with TestClient(main_module.app) as client:
        health = client.get("/health")

    assert health.status_code == 503
    body = health.json()
    assert body["status"] == "degraded"
    assert body["database"]["ready"] is False
    assert body["database"]["missing_tables"] == ["webhook_endpoints", "webhook_deliveries"]
