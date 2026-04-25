from __future__ import annotations

import pytest

from neft_logistics_service.providers import get_compute_provider, get_transport_provider
from neft_logistics_service.providers.base import ProviderUnavailableError
from neft_logistics_service.providers.mock import MockProvider
from neft_logistics_service.providers.osrm import OSRMProvider
from neft_logistics_service.settings import Settings


def test_compute_provider_defaults_to_osrm_when_transport_defaults_to_integration_hub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOGISTICS_PROVIDER", raising=False)
    monkeypatch.delenv("LOGISTICS_COMPUTE_PROVIDER", raising=False)
    settings = Settings(app_env="prod", use_mock_logistics=False)

    assert settings.provider == "integration_hub"
    assert settings.compute_provider == "osrm"


def test_compute_provider_reuses_explicit_mock_transport_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGISTICS_PROVIDER", "mock")
    monkeypatch.delenv("LOGISTICS_COMPUTE_PROVIDER", raising=False)
    settings = Settings(app_env="dev", use_mock_logistics=True)

    assert settings.provider == "mock"
    assert settings.compute_provider == "mock"


def test_provider_selection_is_split_by_ownership() -> None:
    assert isinstance(get_transport_provider("mock"), MockProvider)
    assert isinstance(get_transport_provider("stub"), MockProvider)
    assert isinstance(get_compute_provider("mock"), MockProvider)
    assert isinstance(get_compute_provider("stub"), MockProvider)
    assert isinstance(get_compute_provider("osrm"), OSRMProvider)
    with pytest.raises(ValueError, match="unsupported_transport_provider:osrm"):
        get_transport_provider("osrm")


@pytest.mark.parametrize(
    ("mode", "owner"),
    [("disabled", "logistics_transport"), ("degraded", "logistics_transport")],
)
def test_transport_disabled_and_degraded_modes_are_explicit_runtime_states(mode: str, owner: str) -> None:
    provider = get_transport_provider(mode)

    with pytest.raises(ProviderUnavailableError) as exc:
        provider.trip_get_status("trip-1")

    assert exc.value.code == f"{owner}_{mode}"
    assert exc.value.provider == owner
    assert exc.value.mode == mode


@pytest.mark.parametrize(
    ("mode", "owner"),
    [("disabled", "logistics_compute"), ("degraded", "logistics_compute")],
)
def test_compute_disabled_and_degraded_modes_are_explicit_runtime_states(mode: str, owner: str) -> None:
    provider = get_compute_provider(mode)

    with pytest.raises(ProviderUnavailableError) as exc:
        provider.preview_route(None)

    assert exc.value.code == f"{owner}_{mode}"
    assert exc.value.provider == owner
    assert exc.value.mode == mode
