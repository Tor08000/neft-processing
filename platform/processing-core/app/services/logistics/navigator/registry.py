from __future__ import annotations

from app.config import settings
from app.services.logistics.navigator.base import NavigatorAdapter
from app.services.logistics.navigator.noop import NoopNavigator
from app.services.logistics.navigator.osm_stub import OSMStubNavigator
from app.services.logistics.navigator.yandex_stub import YandexStubNavigator


_ADAPTERS: dict[str, NavigatorAdapter] = {
    "noop": NoopNavigator(),
    "yandex": YandexStubNavigator(),
    "osm": OSMStubNavigator(),
}


def is_enabled() -> bool:
    return settings.LOGISTICS_NAVIGATOR_ENABLED


def get(provider: str | None = None) -> NavigatorAdapter:
    choice = (provider or settings.LOGISTICS_NAVIGATOR_PROVIDER or "noop").lower()
    return _ADAPTERS.get(choice, _ADAPTERS["noop"])


__all__ = ["get", "is_enabled"]
