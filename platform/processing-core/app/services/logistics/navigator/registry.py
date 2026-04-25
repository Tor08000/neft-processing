from __future__ import annotations

import os

from app.config import settings
from app.services.logistics.navigator.base import NavigatorAdapter
from app.services.logistics.navigator.noop import NoopNavigator
from app.services.logistics.navigator.osm_stub import OSMStubNavigator
from app.services.logistics.navigator.yandex_stub import YandexStubNavigator


# Processing-core navigator is a local snapshot/evidence layer only.
# It is not a real routing transport registry and intentionally does not own external providers.
_ADAPTERS: dict[str, NavigatorAdapter] = {
    "noop": NoopNavigator(),
}

_STUB_ADAPTERS: dict[str, NavigatorAdapter] = {
    "yandex_stub": YandexStubNavigator(),
    "osm_stub": OSMStubNavigator(),
}

_UNWIRED_REAL_PROVIDERS: dict[str, str] = {
    "yandex": "yandex_stub",
    "osm": "osm_stub",
}


def is_enabled() -> bool:
    return settings.LOGISTICS_NAVIGATOR_ENABLED


def _stub_providers_allowed() -> bool:
    app_env = (settings.APP_ENV or "dev").strip().lower()
    allow_override = os.getenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "0").strip() == "1"
    return app_env not in {"prod", "production"} or allow_override


def registered_provider_names() -> tuple[str, ...]:
    return tuple(sorted([*_ADAPTERS.keys(), *_STUB_ADAPTERS.keys()]))


def can_replay_locally(provider: str | None) -> bool:
    choice = (provider or "noop").strip().lower()
    return choice in _ADAPTERS or choice in _STUB_ADAPTERS


def get_local_evidence_adapter(provider: str | None = None) -> NavigatorAdapter:
    # Local replay over persisted geometry/evidence may outlive the original compute owner.
    # External preview providers are intentionally reduced to the in-core noop adapter here.
    choice = (provider or "noop").strip().lower()
    if choice in _ADAPTERS:
        return _ADAPTERS[choice]
    if choice in _STUB_ADAPTERS:
        return _STUB_ADAPTERS[choice]
    return _ADAPTERS["noop"]


def get(provider: str | None = None) -> NavigatorAdapter:
    choice = (provider or settings.LOGISTICS_NAVIGATOR_PROVIDER or "noop").strip().lower()
    if choice in _ADAPTERS:
        return _ADAPTERS[choice]
    if choice in _STUB_ADAPTERS:
        if not _stub_providers_allowed():
            raise ValueError(f"logistics_navigator_stub_not_allowed:{choice}")
        return _STUB_ADAPTERS[choice]
    if choice in _UNWIRED_REAL_PROVIDERS:
        explicit_stub = _UNWIRED_REAL_PROVIDERS[choice]
        raise ValueError(
            f"logistics_navigator_provider_unconfigured:{choice}; "
            f"use noop for the in-core fallback or {explicit_stub} only in non-prod"
        )
    return _ADAPTERS["noop"]


__all__ = ["can_replay_locally", "get", "get_local_evidence_adapter", "is_enabled", "registered_provider_names"]
