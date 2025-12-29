from __future__ import annotations

from app.models.unified_explain import PrimaryReason
from app.schemas.admin.unified_explain import FleetAssistantResponse, UnifiedExplainResponse
from app.services.explain.actions import ActionItem
from app.services.explain.escalation import EscalationInfo
from app.services.explain.sla import SLAClock
from app.services.fleet_assistant.prompts import (
    ACTION_EFFECT_PREFIX,
    ACTION_PREFIX,
    ESCALATION_PREFIX,
    SLA_PREFIX,
)
from app.services.fleet_assistant.scenarios import SCENARIOS, InsightScenario


CONFIDENCE_BY_REASON: dict[PrimaryReason, int] = {
    PrimaryReason.LOGISTICS: 72,
    PrimaryReason.RISK: 68,
    PrimaryReason.LIMIT: 74,
    PrimaryReason.MONEY: 66,
    PrimaryReason.POLICY: 64,
    PrimaryReason.UNKNOWN: 40,
}

ACTION_EFFECT_BY_REASON: dict[PrimaryReason, int] = {
    PrimaryReason.LOGISTICS: 32,
    PrimaryReason.RISK: 28,
    PrimaryReason.LIMIT: 41,
    PrimaryReason.MONEY: 30,
    PrimaryReason.POLICY: 25,
    PrimaryReason.UNKNOWN: 18,
}


def build_fleet_assistant(explain: UnifiedExplainResponse) -> FleetAssistantResponse:
    scenario = SCENARIOS.get(explain.primary_reason, SCENARIOS[PrimaryReason.UNKNOWN])
    action = _select_primary_action(explain.actions)
    confidence = CONFIDENCE_BY_REASON.get(explain.primary_reason, 40)
    action_effect_pct = ACTION_EFFECT_BY_REASON.get(explain.primary_reason)
    action_line = _format_action_line(action, action_effect_pct)
    sla_line = _format_sla_line(explain.sla, explain.escalation)
    confidence_line = f"Уверенность: {confidence}%."

    def build_answer(text: str) -> str:
        parts = [text, action_line, confidence_line, sla_line]
        return " ".join(part for part in parts if part)

    return FleetAssistantResponse(
        primary_insight=scenario.insight,
        action=action,
        action_effect_pct=action_effect_pct,
        confidence=confidence,
        sla=explain.sla,
        escalation=explain.escalation,
        answers={
            "why_problem": build_answer(scenario.why_problem),
            "if_ignore": build_answer(scenario.if_ignore),
            "first_action": build_answer(scenario.first_action),
            "trend": build_answer(scenario.trend),
        },
    )


def _select_primary_action(actions: list[ActionItem]) -> ActionItem | None:
    if not actions:
        return None
    required = [action for action in actions if action.severity == "REQUIRED"]
    return required[0] if required else actions[0]


def _format_action_line(action: ActionItem | None, action_effect_pct: int | None) -> str | None:
    if not action:
        return "Рекомендованное действие не найдено."
    effect_part = ""
    if action_effect_pct is not None:
        effect_part = f" {ACTION_EFFECT_PREFIX}: +{action_effect_pct}% случаев IMPROVED."
    return f"{ACTION_PREFIX} {action.title}.{effect_part}".strip()


def _format_sla_line(sla: SLAClock | None, escalation: EscalationInfo | None) -> str | None:
    target = escalation.target if escalation else None
    if sla:
        remaining = _format_remaining_time(sla.remaining_minutes)
        if target:
            return f"{SLA_PREFIX} {remaining} — {ESCALATION_PREFIX} {target}."
        return f"{SLA_PREFIX} {remaining}."
    if target:
        return f"SLA не задан, но {ESCALATION_PREFIX} {target}."
    return "SLA не задан."


def _format_remaining_time(minutes: int) -> str:
    if minutes >= 60:
        hours = max(1, minutes // 60)
        return f"{hours} ч"
    return f"{minutes} мин"


__all__ = ["build_fleet_assistant"]
