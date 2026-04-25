from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from app.settings import get_settings
from app.sign.providers.base import SignProvider
from app.sign.providers.provider_x import (
    DegradedProviderX,
    MockProviderX,
    ProviderX,
    ProviderXConfig,
    has_real_provider_x_credentials,
)


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


def _build_provider_x() -> SignProvider:
    settings = get_settings()
    mode = (settings.provider_x_mode or "").strip().lower()
    if mode in {"mock", "stub"}:
        return MockProviderX()
    if mode in {"degraded", "disabled"}:
        return DegradedProviderX()
    if mode in {"real", "prod", "production", "sandbox"}:
        base_url_source = settings.provider_x_sandbox_base_url if mode == "sandbox" else settings.provider_x_base_url
        base_url = (base_url_source or "").strip().rstrip("/")
        if not base_url or not has_real_provider_x_credentials(settings.provider_x_api_key, settings.provider_x_api_secret):
            raise RuntimeError("provider_x_unconfigured")
        return ProviderX(
            ProviderXConfig(
                base_url=base_url,
                api_key=settings.provider_x_api_key,
                api_secret=settings.provider_x_api_secret,
                timeout_seconds=settings.provider_x_timeout_seconds,
            )
        )
    raise RuntimeError(f"unsupported_provider_x_mode:{mode or 'empty'}")


def build_default_registry() -> ProviderRegistry:
    registry = ProviderRegistry(providers={})
    registry.register("provider_x", _build_provider_x())
    registry.register("esign_provider", _build_provider_x())
    return registry


def refresh_default_registry() -> ProviderRegistry:
    global _default_registry
    _default_registry = build_default_registry()
    return _default_registry


def get_registry() -> ProviderRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_registry()
    return _default_registry


__all__ = ["ProviderRegistry", "get_registry", "build_default_registry", "refresh_default_registry"]
