from __future__ import annotations

import pytest

from app.sign.providers.provider_x import DegradedProviderX, MockProviderX, ProviderX
from app.sign.registry import build_default_registry


def test_registry_uses_mock_provider_only_when_mode_is_explicit_mock(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_X_MODE", "mock")
    monkeypatch.delenv("PROVIDER_X_BASE_URL", raising=False)

    registry = build_default_registry()

    assert isinstance(registry.get("provider_x"), MockProviderX)


def test_registry_treats_stub_as_explicit_mock_alias(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_X_MODE", "stub")
    monkeypatch.delenv("PROVIDER_X_BASE_URL", raising=False)

    registry = build_default_registry()

    assert isinstance(registry.get("provider_x"), MockProviderX)


@pytest.mark.parametrize("mode", ["real", "prod", "production"])
def test_registry_uses_real_provider_when_mode_and_base_url_are_explicit(monkeypatch, mode: str) -> None:
    monkeypatch.setenv("PROVIDER_X_MODE", mode)
    monkeypatch.setenv("PROVIDER_X_BASE_URL", "https://provider-x.example.test")
    monkeypatch.setenv("PROVIDER_X_API_KEY", "provider-key")
    monkeypatch.setenv("PROVIDER_X_API_SECRET", "provider-secret")

    registry = build_default_registry()

    assert isinstance(registry.get("provider_x"), ProviderX)


@pytest.mark.parametrize("mode", ["real", "prod", "production"])
def test_registry_fails_fast_when_real_provider_is_unconfigured(monkeypatch, mode: str) -> None:
    monkeypatch.setenv("PROVIDER_X_MODE", mode)
    monkeypatch.delenv("PROVIDER_X_BASE_URL", raising=False)
    monkeypatch.delenv("PROVIDER_X_API_KEY", raising=False)
    monkeypatch.delenv("PROVIDER_X_API_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="provider_x_unconfigured"):
        build_default_registry()


@pytest.mark.parametrize("missing_name", ["PROVIDER_X_API_KEY", "PROVIDER_X_API_SECRET"])
def test_registry_fails_fast_when_real_provider_credentials_are_missing(monkeypatch, missing_name: str) -> None:
    monkeypatch.setenv("PROVIDER_X_MODE", "real")
    monkeypatch.setenv("PROVIDER_X_BASE_URL", "https://provider-x.example.test")
    monkeypatch.setenv("PROVIDER_X_API_KEY", "provider-key")
    monkeypatch.setenv("PROVIDER_X_API_SECRET", "provider-secret")
    monkeypatch.delenv(missing_name, raising=False)

    with pytest.raises(RuntimeError, match="provider_x_unconfigured"):
        build_default_registry()


@pytest.mark.parametrize("mode", ["degraded", "disabled"])
def test_registry_uses_degraded_provider_when_mode_is_explicit(monkeypatch, mode: str) -> None:
    monkeypatch.setenv("PROVIDER_X_MODE", mode)
    monkeypatch.delenv("PROVIDER_X_BASE_URL", raising=False)

    registry = build_default_registry()

    assert isinstance(registry.get("provider_x"), DegradedProviderX)


def test_registry_uses_sandbox_provider_when_sandbox_url_is_explicit(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_X_MODE", "sandbox")
    monkeypatch.setenv("PROVIDER_X_SANDBOX_BASE_URL", "https://provider-x-sandbox.example.test")
    monkeypatch.setenv("PROVIDER_X_API_KEY", "provider-key")
    monkeypatch.setenv("PROVIDER_X_API_SECRET", "provider-secret")

    registry = build_default_registry()

    assert isinstance(registry.get("provider_x"), ProviderX)


def test_registry_fails_fast_for_unsupported_mode(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_X_MODE", "unsupported-vendor")
    monkeypatch.setenv("PROVIDER_X_BASE_URL", "https://provider-x.example.test")
    monkeypatch.setenv("PROVIDER_X_API_KEY", "provider-key")
    monkeypatch.setenv("PROVIDER_X_API_SECRET", "provider-secret")

    with pytest.raises(RuntimeError, match="unsupported_provider_x_mode:unsupported-vendor"):
        build_default_registry()
