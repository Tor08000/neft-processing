from __future__ import annotations

QUESTION_LABELS = {
    "why_problem": "Почему сейчас это проблема?",
    "if_ignore": "Что будет, если ничего не делать?",
    "first_action": "Что лучше сделать первым?",
    "trend": "Это ухудшается или стабильно?",
    "benchmark": "Это нормально или хуже, чем у других?",
}

ACTION_PREFIX = "Рекомендую начать с"
ACTION_EFFECT_PREFIX = "Эффект от аналогичных действий"
SLA_PREFIX = "Если не сделать за"
ESCALATION_PREFIX = "эскалация в"

__all__ = [
    "ACTION_EFFECT_PREFIX",
    "ACTION_PREFIX",
    "ESCALATION_PREFIX",
    "QUESTION_LABELS",
    "SLA_PREFIX",
]
