from __future__ import annotations

from neft_integration_hub.providers.base import EdoProviderAdapter
from neft_integration_hub.providers.diadok import MockDiadokProvider, ProdDiadokProvider
from neft_integration_hub.settings import get_settings


class ProviderRegistry:
    def __init__(self) -> None:
        settings = get_settings()
        diadok_provider = MockDiadokProvider()
        if settings.diadok_mode.lower() == "prod":
            diadok_provider = ProdDiadokProvider()
        self._providers: dict[str, EdoProviderAdapter] = {
            "DIADOK": diadok_provider,
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
