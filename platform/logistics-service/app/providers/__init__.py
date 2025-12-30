from __future__ import annotations

from app.providers.base import BaseProvider
from app.providers.mock import MockProvider


def get_provider(name: str) -> BaseProvider:
    if name == MockProvider.name:
        return MockProvider()
    raise ValueError(f"unknown_provider:{name}")


__all__ = ["BaseProvider", "MockProvider", "get_provider"]
