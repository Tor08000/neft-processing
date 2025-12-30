from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from app.settings import get_settings
from app.sign.providers.base import SignProvider
from app.sign.providers.provider_x import MockProviderX, ProviderX

settings = get_settings()


@dataclass
class ProviderRegistry:
    providers: Dict[str, SignProvider]

    def register(self, name: str, provider: SignProvider) -> None:
        self.providers[name] = provider

    def get(self, name: str) -> SignProvider:
        provider = self.providers.get(name)
        if provider is None:
            raise KeyError("provider_not_found")
        return provider


_default_registry: ProviderRegistry | None = None


def build_default_registry() -> ProviderRegistry:
    registry = ProviderRegistry(providers={})
    if settings.provider_x_mode == "mock" or not settings.provider_x_base_url:
        registry.register("provider_x", MockProviderX())
    else:
        registry.register("provider_x", ProviderX())
    return registry


def get_registry() -> ProviderRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_registry()
    return _default_registry


__all__ = ["ProviderRegistry", "get_registry", "build_default_registry"]
