from __future__ import annotations

from app.providers.base import EdoProviderAdapter
from app.providers.diadok import MockDiadokProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, EdoProviderAdapter] = {
            "DIADOK": MockDiadokProvider(),
        }

    def get(self, provider: str) -> EdoProviderAdapter:
        if provider not in self._providers:
            raise KeyError(provider)
        return self._providers[provider]


_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


__all__ = ["ProviderRegistry", "get_registry"]
