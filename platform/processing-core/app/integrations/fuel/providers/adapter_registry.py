from __future__ import annotations

from collections.abc import Iterable

from app.integrations.fuel.providers.protocols import FuelProvider


_PROVIDERS: dict[str, FuelProvider] = {}


def register_provider(provider: FuelProvider) -> None:
    _PROVIDERS[provider.code] = provider


def get_provider(code: str) -> FuelProvider:
    provider = _PROVIDERS.get(code)
    if not provider:
        raise KeyError(f"Fuel provider adapter not registered: {code}")
    return provider


def list_providers() -> Iterable[FuelProvider]:
    return _PROVIDERS.values()


def load_default_providers() -> None:
    from app.integrations.fuel.providers.provider_ref.adapter import ProviderRefAdapter

    register_provider(ProviderRefAdapter())
