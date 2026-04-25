from __future__ import annotations

from neft_integration_hub.providers.base import EdoProviderAdapter, ProviderDegradedError
from neft_integration_hub.providers.diadok import (
    MockDiadokProvider,
    MockSbisProvider,
    ProdDiadokProvider,
    UnavailableDiadokProvider,
)
from neft_integration_hub.settings import get_settings


def _build_diadok_provider(mode: str) -> EdoProviderAdapter:
    normalized = (mode or "").strip().lower()
    if normalized in {"mock", "stub", "sandbox"}:
        return MockDiadokProvider()
    if normalized in {"disabled", "degraded"}:
        return UnavailableDiadokProvider(normalized)
    if normalized in {"real", "prod", "production"}:
        return ProdDiadokProvider()
    raise RuntimeError(f"unsupported_diadok_mode:{normalized or 'empty'}")


def _build_sbis_provider(mode: str) -> EdoProviderAdapter:
    normalized = (mode or "").strip().lower()
    if normalized in {"mock", "stub", "sandbox"}:
        return MockSbisProvider()
    if normalized in {"disabled", "degraded", "unsupported"}:
        return UnavailableDiadokProvider(normalized, provider="SBIS")
    raise RuntimeError(f"unsupported_sbis_mode:{normalized or 'empty'}")


class ProviderRegistry:
    def __init__(self) -> None:
        settings = get_settings()
        self._providers: dict[str, EdoProviderAdapter] = {
            "DIADOK": _build_diadok_provider(settings.diadok_mode),
            "SBIS": _build_sbis_provider(settings.sbis_mode),
        }

    def get(self, provider: str) -> EdoProviderAdapter:
        if provider not in self._providers:
            raise ProviderDegradedError(
                f"Provider {provider} is not wired in integration-hub",
                code=f"provider_not_supported:{provider.lower()}",
                provider=provider,
            )
        return self._providers[provider]


_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


__all__ = ["ProviderRegistry", "get_registry"]
