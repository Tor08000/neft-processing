from __future__ import annotations

import pytest

from neft_integration_hub.providers.base import ProviderDegradedError
from neft_integration_hub.providers.diadok import (
    MockDiadokProvider,
    MockSbisProvider,
    ProdDiadokProvider,
    UnavailableDiadokProvider,
)
from neft_integration_hub.providers.registry import _build_diadok_provider, _build_sbis_provider


@pytest.mark.parametrize("mode", ["mock", "stub", "sandbox"])
def test_diadok_registry_keeps_mock_modes_explicit(mode: str) -> None:
    assert isinstance(_build_diadok_provider(mode), MockDiadokProvider)


@pytest.mark.parametrize("mode", ["real", "prod", "production"])
def test_diadok_registry_uses_provider_backed_modes(mode: str) -> None:
    assert isinstance(_build_diadok_provider(mode), ProdDiadokProvider)


def test_sbis_registry_uses_sandbox_provider_without_diadok_fallback() -> None:
    provider = _build_sbis_provider("sandbox")

    assert isinstance(provider, MockSbisProvider)
    assert provider.send(b"payload", {}).startswith("sandbox-sbis-")


@pytest.mark.parametrize("mode", ["disabled", "degraded"])
def test_diadok_registry_surfaces_unavailable_modes(mode: str) -> None:
    provider = _build_diadok_provider(mode)

    assert isinstance(provider, UnavailableDiadokProvider)
    with pytest.raises(ProviderDegradedError) as exc:
        provider.send(b"payload", {})

    assert exc.value.code == f"diadok_{mode}"
    assert exc.value.provider == "DIADOK"


def test_sbis_registry_surfaces_unavailable_modes_without_diadok_alias() -> None:
    provider = _build_sbis_provider("degraded")

    assert isinstance(provider, UnavailableDiadokProvider)
    with pytest.raises(ProviderDegradedError) as exc:
        provider.send(b"payload", {})

    assert exc.value.code == "sbis_degraded"
    assert exc.value.provider == "SBIS"


def test_diadok_provider_fails_before_network_with_placeholder_config() -> None:
    provider = ProdDiadokProvider(base_url="https://diadok.example.com", api_token="change-me")

    with pytest.raises(ProviderDegradedError) as exc:
        provider.send(b"payload", {})

    assert exc.value.code == "diadok_unconfigured"
    assert exc.value.provider == "DIADOK"
