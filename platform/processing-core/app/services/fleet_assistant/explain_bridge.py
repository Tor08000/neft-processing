from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.fleet_intelligence_actions import FIActionCode
from app.models.unified_explain import PrimaryReason
from app.schemas.admin.unified_explain import (
    FleetAssistantProjection,
    FleetAssistantResponse,
    UnifiedExplainResponse,
)
from app.services.explain.actions import ActionItem
from app.services.explain.escalation import EscalationInfo
from app.services.explain.sla import SLAClock
from app.services.fleet_assistant.benchmarks import build_benchmark_response
from app.services.fleet_assistant.projections import build_outcome_projection
from app.services.fleet_assistant.prompts import (
    ACTION_EFFECT_PREFIX,
    ACTION_PREFIX,
    ESCALATION_PREFIX,
    SLA_PREFIX,
)
from app.services.fleet_assistant.scenarios import SCENARIOS, InsightScenario
from app.services.fleet_intelligence.control import defaults as control_defaults
from app.services.fleet_intelligence.control import repository as control_repository


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


def build_fleet_assistant(explain: UnifiedExplainResponse, db: Session | None = None) -> FleetAssistantResponse:
    scenario = SCENARIOS.get(explain.primary_reason, SCENARIOS[PrimaryReason.UNKNOWN])
    action = _select_primary_action(explain.actions)
    confidence = CONFIDENCE_BY_REASON.get(explain.primary_reason, 40)
    action_effect_pct = ACTION_EFFECT_BY_REASON.get(explain.primary_reason)
    action_line = _format_action_line(action, action_effect_pct)
    sla_line = _format_sla_line(explain.sla, explain.escalation)
    confidence_line = f"Уверенность: {confidence}%."
    projection = _build_projection(explain, db=db)
    projection_text = _format_projection_text(projection)
    benchmark_result = build_benchmark_response(explain, db=db)
    benchmark = benchmark_result.benchmark if benchmark_result else None
    benchmark_answer = benchmark_result.answer if benchmark_result else None
    if not benchmark_answer:
        benchmark_answer = "Данные для сравнения недоступны."

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
        projection=projection,
        benchmark=benchmark,
        answers={
            "why_problem": build_answer(scenario.why_problem),
            "if_ignore": build_answer(scenario.if_ignore),
            "first_action": build_answer(scenario.first_action),
            "trend": build_answer(scenario.trend),
            "what_happens": projection_text,
            "benchmark": benchmark_answer,
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


def _build_projection(explain: UnifiedExplainResponse, *, db: Session | None) -> FleetAssistantProjection:
    fleet_control = _get_fleet_control_section(explain)
    suggested_action = _select_confidence_action(fleet_control)
    confidence = _resolve_confidence(suggested_action)
    sample_size = _resolve_sample_size(db, suggested_action)
    trend_label = _resolve_trend_label(explain)
    entity_type = _resolve_entity_type(explain, fleet_control)
    sla_remaining_minutes = explain.sla.remaining_minutes if explain.sla else None
    aging_days = _resolve_aging_days(fleet_control)
    insight_status = _resolve_insight_status(fleet_control)
    half_life_days = _resolve_half_life(suggested_action)
    return build_outcome_projection(
        confidence=confidence,
        sample_size=sample_size,
        trend_label=trend_label,
        entity_type=entity_type,
        sla_remaining_minutes=sla_remaining_minutes,
        aging_days=aging_days,
        insight_status=insight_status,
        half_life_days=half_life_days,
    )


def _format_projection_text(projection: FleetAssistantProjection) -> str:
    if not projection:
        return "Данные для прогнозирования недоступны."
    applied = projection.if_applied
    ignored = projection.if_ignored
    applied_line = (
        f"Если применить действие сейчас, вероятность улучшения ~{applied.probability_improved_pct}% "
        f"за {applied.expected_time_window_days} дней."
    )
    ignored_line = _format_ignored_line(ignored)
    return " ".join([applied_line, ignored_line]).strip()


def _format_ignored_line(ignored) -> str:
    escalation = ignored.escalation_risk
    if escalation.likely and escalation.eta_minutes is not None:
        remaining = _format_remaining_time(escalation.eta_minutes)
        return f"Если игнорировать, высок риск эскалации через ~{remaining}."
    if escalation.likely:
        return "Если игнорировать, высок риск эскалации."
    return "Если игнорировать, эскалация маловероятна."


def _get_fleet_control_section(explain: UnifiedExplainResponse) -> dict | None:
    fleet_control = explain.sections.get("fleet_control")
    return fleet_control if isinstance(fleet_control, dict) else None


def _select_confidence_action(fleet_control: dict | None) -> dict | None:
    if not fleet_control:
        return None
    suggested = fleet_control.get("suggested_actions")
    if not isinstance(suggested, list) or not suggested:
        return None
    def _confidence_value(item: dict) -> float:
        value = item.get("confidence")
        return float(value) if isinstance(value, (int, float)) else -1.0
    return max(suggested, key=_confidence_value)


def _resolve_confidence(action: dict | None) -> float | None:
    if not action:
        return None
    value = action.get("confidence")
    return float(value) if isinstance(value, (int, float)) else None


def _resolve_half_life(action: dict | None) -> int:
    if not action:
        return control_defaults.CONF_HALF_LIFE_DAYS
    value = action.get("confidence_half_life_days")
    return int(value) if isinstance(value, int) else control_defaults.CONF_HALF_LIFE_DAYS


def _resolve_sample_size(db: Session | None, action: dict | None) -> int | None:
    if not db or not action:
        value = action.get("confidence_improved_count") if action else None
        return int(value) if isinstance(value, int) else None
    action_code = action.get("action_code")
    if not isinstance(action_code, str):
        return None
    try:
        resolved_code = FIActionCode(action_code)
    except ValueError:
        return None
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=control_defaults.CONFIDENCE_WINDOW_DAYS)
    effects = control_repository.list_action_effects_for_action_code(db, action_code=resolved_code, cutoff=cutoff)
    return len(effects)


def _resolve_trend_label(explain: UnifiedExplainResponse) -> str | None:
    fleet_trends = explain.sections.get("fleet_trends")
    if not isinstance(fleet_trends, dict):
        return None
    entity_type = _resolve_entity_type(explain, _get_fleet_control_section(explain))
    trend_payload = None
    if entity_type == "DRIVER":
        trend_payload = fleet_trends.get("driver")
    elif entity_type == "STATION":
        trend_payload = fleet_trends.get("station")
    elif entity_type == "VEHICLE":
        trend_payload = fleet_trends.get("vehicle")
    if isinstance(trend_payload, dict):
        label = trend_payload.get("label")
        return str(label) if label else None
    return None


def _resolve_entity_type(explain: UnifiedExplainResponse, fleet_control: dict | None) -> str | None:
    if fleet_control:
        active = fleet_control.get("active_insight")
        if isinstance(active, dict) and active.get("entity_type"):
            return str(active.get("entity_type"))
    subject = explain.subject
    if subject.driver_id:
        return "DRIVER"
    if subject.station_id:
        return "STATION"
    if subject.vehicle_id:
        return "VEHICLE"
    return None


def _resolve_aging_days(fleet_control: dict | None) -> int | None:
    if not fleet_control:
        return None
    aging = fleet_control.get("aging")
    if isinstance(aging, dict) and isinstance(aging.get("days_open"), int):
        return int(aging.get("days_open"))
    return None


def _resolve_insight_status(fleet_control: dict | None) -> str | None:
    if not fleet_control:
        return None
    active = fleet_control.get("active_insight")
    if isinstance(active, dict) and active.get("status"):
        return str(active.get("status"))
    return None


__all__ = ["build_fleet_assistant"]
