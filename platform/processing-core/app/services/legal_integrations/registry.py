from __future__ import annotations

from collections.abc import Iterable

from app.services.legal_integrations.base import ExternalLegalAdapter
from app.services.legal_integrations.errors import ProviderNotConfigured


class LegalAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ExternalLegalAdapter] = {}

    def register(self, adapter: ExternalLegalAdapter) -> None:
        self._adapters[adapter.provider] = adapter

    def get(self, provider: str) -> ExternalLegalAdapter:
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise ProviderNotConfigured(f"adapter_not_registered:{provider}")
        return adapter

    def providers(self) -> Iterable[str]:
        return self._adapters.keys()


registry = LegalAdapterRegistry()


__all__ = ["LegalAdapterRegistry", "registry"]
