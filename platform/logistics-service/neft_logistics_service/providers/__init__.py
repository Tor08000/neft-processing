from __future__ import annotations

from neft_logistics_service.providers.base import BaseProvider
from neft_logistics_service.providers.integration_hub_provider import IntegrationHubProvider
from neft_logistics_service.providers.mock import MockProvider
from neft_logistics_service.providers.osrm import OSRMProvider
from neft_logistics_service.providers.unavailable import UnavailableProvider


def get_transport_provider(name: str) -> BaseProvider:
    normalized = (name or "").strip().lower()
    if normalized in {MockProvider.name, "stub"}:
        return MockProvider()
    if normalized == IntegrationHubProvider.name:
        return IntegrationHubProvider()
    if normalized in {"disabled", "degraded"}:
        return UnavailableProvider(normalized, "logistics_transport")
    raise ValueError(f"unsupported_transport_provider:{normalized or 'empty'}")


def get_compute_provider(name: str) -> BaseProvider:
    normalized = (name or "").strip().lower()
    if normalized in {MockProvider.name, "stub"}:
        return MockProvider()
    if normalized == OSRMProvider.name:
        return OSRMProvider()
    if normalized in {"disabled", "degraded"}:
        return UnavailableProvider(normalized, "logistics_compute")
    raise ValueError(f"unsupported_compute_provider:{normalized or 'empty'}")


def get_provider(name: str) -> BaseProvider:
    return get_transport_provider(name)


__all__ = [
    "BaseProvider",
    "MockProvider",
    "OSRMProvider",
    "IntegrationHubProvider",
    "UnavailableProvider",
    "get_compute_provider",
    "get_provider",
    "get_transport_provider",
]
