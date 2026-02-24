from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main


def test_startup_allows_mock_provider_in_dev(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    object.__setattr__(main.settings, "provider_x_mode", "mock")

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_startup_fails_in_prod_with_mock_provider(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("ALLOW_MOCK_PROVIDERS_IN_PROD", raising=False)
    object.__setattr__(main.settings, "provider_x_mode", "mock")

    with pytest.raises(RuntimeError, match="prod guardrail violation"):
        with TestClient(main.app):
            pass
