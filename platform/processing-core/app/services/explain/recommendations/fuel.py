from __future__ import annotations

from typing import Iterable

from app.services.explain.recommendations import common

FUEL_RECOMMENDATIONS = {
    "LIMIT_EXCEEDED_AMOUNT": "Проверьте лимит клиента на период",
    "DAILY": "Транзакция превышает дневной лимит",
    "FUEL_OFF_ROUTE_STRONG": "Заправка произведена вне маршрута",
}


def _map_recommendations(keys: Iterable[str]) -> list[str]:
    return list(filter(None, (FUEL_RECOMMENDATIONS.get(key) for key in keys)))


def build_recommendations(explain_snapshot: dict) -> list[str]:
    keys = explain_snapshot.get("signals", []) or []
    keys += explain_snapshot.get("limit_flags", []) or []
    mapped = _map_recommendations(keys)
    return mapped + common.build_recommendations(explain_snapshot)


__all__ = ["build_recommendations"]
