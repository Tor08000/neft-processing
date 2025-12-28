from __future__ import annotations

from typing import Iterable

from app.services.explain.recommendations import common

LOGISTICS_RECOMMENDATIONS = {
    "OFF_ROUTE": "Маршрут отклонён более чем на 12 км",
    "FUEL_STOP_MISMATCH": "Заправка произведена вне маршрута",
}


def _map_recommendations(keys: Iterable[str]) -> list[str]:
    return list(filter(None, (LOGISTICS_RECOMMENDATIONS.get(key) for key in keys)))


def build_recommendations(explain_snapshot: dict) -> list[str]:
    keys = explain_snapshot.get("signals", []) or []
    mapped = _map_recommendations(keys)
    return mapped + common.build_recommendations(explain_snapshot)


__all__ = ["build_recommendations"]
