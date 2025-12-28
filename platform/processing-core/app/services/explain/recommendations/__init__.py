from __future__ import annotations

from app.models.unified_explain import PrimaryReason

RECOMMENDATION_TEMPLATES = {
    "INCREASE_LIMIT": "Запросить повышение лимита",
    "CHANGE_LIMIT_PROFILE": "Обновить профиль лимитов клиента",
    "CHECK_CONTRACT": "Проверить условия договора",
    "REQUEST_OVERRIDE": "Запросить override решения",
    "CHECK_COMPLIANCE": "Проверить соответствие комплаенсу",
    "RUN_REPLAY": "Запустить money replay",
    "ADJUST_ROUTE": "Скорректировать маршрут",
    "CHECK_TRACKING": "Проверить трекинг транспорта",
    "VERIFY_STOP": "Подтвердить остановку",
    "CHECK_LEDGER": "Проверить проводки в леджере",
    "CHECK_INVARIANTS": "Проверить инварианты биллинга",
}

PRIMARY_REASON_RECOMMENDATIONS = {
    PrimaryReason.LIMIT: ["INCREASE_LIMIT", "CHANGE_LIMIT_PROFILE", "CHECK_CONTRACT"],
    PrimaryReason.RISK: ["REQUEST_OVERRIDE", "CHECK_COMPLIANCE", "RUN_REPLAY"],
    PrimaryReason.LOGISTICS: ["ADJUST_ROUTE", "CHECK_TRACKING", "VERIFY_STOP"],
    PrimaryReason.MONEY: ["RUN_REPLAY", "CHECK_LEDGER", "CHECK_INVARIANTS"],
}

RECOMMENDATION_SECTION_REQUIREMENTS = {
    "INCREASE_LIMIT": {"limits"},
    "CHANGE_LIMIT_PROFILE": {"limits"},
    "CHECK_CONTRACT": {"documents"},
    "REQUEST_OVERRIDE": {"risk"},
    "CHECK_COMPLIANCE": {"risk"},
    "RUN_REPLAY": {"money"},
    "ADJUST_ROUTE": {"logistics", "navigator"},
    "CHECK_TRACKING": {"logistics", "navigator"},
    "VERIFY_STOP": {"logistics"},
    "CHECK_LEDGER": {"money"},
    "CHECK_INVARIANTS": {"money"},
}

__all__ = [
    "PRIMARY_REASON_RECOMMENDATIONS",
    "RECOMMENDATION_SECTION_REQUIREMENTS",
    "RECOMMENDATION_TEMPLATES",
]
