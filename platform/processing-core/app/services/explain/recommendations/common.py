from __future__ import annotations

from typing import Iterable

COMMON_RECOMMENDATIONS = {
    "manual_confirmation": "Требуется ручное подтверждение администратора",
}


def _map_recommendations(keys: Iterable[str]) -> list[str]:
    return list(filter(None, (COMMON_RECOMMENDATIONS.get(key) for key in keys)))


def build_recommendations(explain_snapshot: dict) -> list[str]:
    keys = explain_snapshot.get("common", []) or []
    return _map_recommendations(keys)


__all__ = ["build_recommendations"]
