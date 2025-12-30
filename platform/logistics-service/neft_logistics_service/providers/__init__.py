from __future__ import annotations

from neft_logistics_service.providers.base import BaseProvider
from neft_logistics_service.providers.mock import MockProvider
from neft_logistics_service.providers.osrm import OSRMProvider


def get_provider(name: str) -> BaseProvider:
    if name == MockProvider.name:
        return MockProvider()
    if name == OSRMProvider.name:
        return OSRMProvider()
    raise ValueError(f"unknown_provider:{name}")


__all__ = ["BaseProvider", "MockProvider", "OSRMProvider", "get_provider"]
