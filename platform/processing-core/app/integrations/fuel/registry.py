from __future__ import annotations

from collections.abc import Iterable
from typing import Type

from app.integrations.fuel.base import FuelProviderConnector

_REGISTRY: dict[str, Type[FuelProviderConnector]] = {}


def register(connector_cls: Type[FuelProviderConnector]) -> Type[FuelProviderConnector]:
    code = getattr(connector_cls, "code", None)
    if not code:
        raise ValueError("Connector code is required")
    _REGISTRY[code] = connector_cls
    return connector_cls


def get_connector(code: str) -> FuelProviderConnector:
    if code not in _REGISTRY:
        raise KeyError(f"provider_not_registered:{code}")
    return _REGISTRY[code]()


def list_providers() -> Iterable[str]:
    return sorted(_REGISTRY.keys())


def load_default_providers() -> None:
    from app.integrations.fuel.providers import http_provider_template, stub_provider  # noqa: F401


__all__ = ["get_connector", "list_providers", "load_default_providers", "register"]
