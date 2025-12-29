from __future__ import annotations

from app.services.decision_memory import defaults as memory_defaults
from app.services.fleet_decision_choice import defaults as decision_choice_defaults
from app.services.fleet_intelligence.taxonomy import ActionHintCode

MAX_CANDIDATES = 3
PROJECTION_WINDOW_DAYS = 7

WEIGHT_PROBABILITY = 0.6
WEIGHT_RISK = 0.2
WEIGHT_PENALTY = 0.2

OUTLOOK_BONUS = {
    "IMPROVE": 1.0,
    "NO_CHANGE": 0.5,
    "UNCERTAIN": 0.2,
}

ACTION_ALIASES = {
    "ADJUST_ROUTE": ActionHintCode.REQUIRE_ROUTE_LINKED_REFUEL.value,
}

ACTION_TITLES = {
    ActionHintCode.RESTRICT_NIGHT_FUELING.value: "Ограничить ночные заправки",
    ActionHintCode.REQUIRE_ROUTE_LINKED_REFUEL.value: "Разрешать заправку только на точках маршрута",
    ActionHintCode.REVIEW_DRIVER_BEHAVIOR.value: "Провести проверку поведения водителя",
    ActionHintCode.CHECK_VEHICLE_FUEL_EFFICIENCY.value: "Проверить топливную эффективность автомобиля",
    ActionHintCode.EXCLUDE_STATION_FROM_ROUTES.value: "Исключить станцию из маршрутов",
    ActionHintCode.MOVE_STATION_TO_WATCHLIST.value: "Перевести станцию в список наблюдения",
    ActionHintCode.REQUEST_COMPLIANCE_REVIEW.value: "Запросить проверку комплаенса",
}

ACTION_DEEPLINKS = {
    ActionHintCode.RESTRICT_NIGHT_FUELING.value: "/crm/limit-profiles",
    ActionHintCode.EXCLUDE_STATION_FROM_ROUTES.value: "/logistics/route-constraints",
    ActionHintCode.CHECK_VEHICLE_FUEL_EFFICIENCY.value: "/fleet/vehicles",
}

ACTION_CATEGORIES = {
    ActionHintCode.RESTRICT_NIGHT_FUELING.value: "DRIVER_BEHAVIOR",
    ActionHintCode.REQUIRE_ROUTE_LINKED_REFUEL.value: "ROUTE_ADHERENCE",
    ActionHintCode.REVIEW_DRIVER_BEHAVIOR.value: "DRIVER_BEHAVIOR",
    ActionHintCode.EXCLUDE_STATION_FROM_ROUTES.value: "STATION_TRUST",
    ActionHintCode.MOVE_STATION_TO_WATCHLIST.value: "STATION_TRUST",
}

DEFAULT_ACTION_CODES = list(decision_choice_defaults.DEFAULT_ACTION_CODES)

MEMORY_WINDOW_DAYS = memory_defaults.MEMORY_WINDOW_DAYS
MEMORY_HALF_LIFE_DAYS = memory_defaults.HALF_LIFE_DAYS

HIGH_PENALTY_PCT = 60

__all__ = [
    "ACTION_ALIASES",
    "ACTION_CATEGORIES",
    "ACTION_DEEPLINKS",
    "ACTION_TITLES",
    "DEFAULT_ACTION_CODES",
    "HIGH_PENALTY_PCT",
    "MAX_CANDIDATES",
    "PROJECTION_WINDOW_DAYS",
    "MEMORY_HALF_LIFE_DAYS",
    "MEMORY_WINDOW_DAYS",
    "OUTLOOK_BONUS",
    "WEIGHT_PENALTY",
    "WEIGHT_PROBABILITY",
    "WEIGHT_RISK",
]
