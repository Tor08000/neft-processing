from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main


def test_startup_allows_mock_provider_in_dev(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("PROVIDER_X_MODE", "mock")
    monkeypatch.delenv("PROVIDER_X_BASE_URL", raising=False)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_startup_fails_in_prod_with_mock_provider(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("PROVIDER_X_MODE", "mock")
    monkeypatch.delenv("ALLOW_MOCK_PROVIDERS_IN_PROD", raising=False)

    with pytest.raises(RuntimeError, match="prod guardrail violation"):
        with TestClient(main.app):
            pass


def test_startup_fails_when_real_provider_is_unconfigured(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("PROVIDER_X_MODE", "real")
    monkeypatch.delenv("PROVIDER_X_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="provider_x_unconfigured"):
        with TestClient(main.app):
            pass


def test_startup_allows_explicit_degraded_provider_mode(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("PROVIDER_X_MODE", "degraded")
    monkeypatch.delenv("PROVIDER_X_BASE_URL", raising=False)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["provider_modes"]["provider_x"] == "degraded"


def test_provider_health_treats_placeholder_credentials_as_degraded(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_X_MODE", "real")
    monkeypatch.setenv("PROVIDER_X_BASE_URL", "https://provider-x.example.test")
    monkeypatch.setenv("PROVIDER_X_API_KEY", "dev-key")
    monkeypatch.setenv("PROVIDER_X_API_SECRET", "dev-secret")

    providers = {item["provider"]: item for item in main._esign_provider_health()}

    assert providers["esign_provider"]["status"] == "DEGRADED"
    assert providers["esign_provider"]["configured"] is False
    assert providers["esign_provider"]["last_error_code"] == "esign_provider_not_configured"
