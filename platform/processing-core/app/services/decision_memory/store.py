from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.decision_memory import DecisionMemoryEffectLabel, DecisionMemoryEntityType, DecisionOutcome
from app.models.fleet_intelligence_actions import FIActionEffect, FIInsight
from app.services.decision_memory import repository


def record_outcome_from_effect(
    db: Session,
    *,
    action,
    insight: FIInsight,
    effect: FIActionEffect,
) -> DecisionOutcome | None:
    if not action or not insight or not effect:
        return None
    outcome = DecisionOutcome(
        tenant_id=insight.tenant_id,
        client_id=insight.client_id,
        entity_type=_map_entity_type(insight.entity_type.value),
        entity_id=str(insight.entity_id),
        insight_id=insight.id,
        applied_action_id=action.id,
        action_code=action.action_code.value,
        bundle_code=None,
        applied_at=action.applied_at,
        measured_at=effect.measured_at,
        window_days=effect.window_days,
        effect_label=_map_effect_label(effect.effect_label.value),
        effect_delta=effect.delta,
        confidence_at_apply=None,
        context=_build_context(insight=insight, effect=effect),
    )
    stored = repository.add_outcome(db, outcome=outcome)
    if stored is outcome:
        repository.upsert_action_stats_daily(
            db,
            tenant_id=outcome.tenant_id,
            client_id=outcome.client_id,
            action_code=outcome.action_code,
            entity_type=outcome.entity_type,
            day=_resolve_stats_day(outcome),
            effect_label=outcome.effect_label,
        )
    return stored


def _resolve_stats_day(outcome: DecisionOutcome) -> datetime.date:
    base = outcome.measured_at or outcome.applied_at
    return base.date()


def _map_entity_type(value: str) -> DecisionMemoryEntityType:
    try:
        return DecisionMemoryEntityType(value)
    except ValueError:
        return DecisionMemoryEntityType.CLIENT


def _map_effect_label(value: str) -> DecisionMemoryEffectLabel:
    try:
        return DecisionMemoryEffectLabel(value)
    except ValueError:
        return DecisionMemoryEffectLabel.UNKNOWN


def _build_context(*, insight: FIInsight, effect: FIActionEffect) -> dict[str, Any]:
    context: dict[str, Any] = {
        "primary_reason": insight.primary_reason.value if insight.primary_reason else None,
        "insight_type": insight.insight_type.value,
        "entity_type": insight.entity_type.value,
        "window_days": insight.window_days,
        "summary": effect.summary,
    }
    return {key: value for key, value in context.items() if value is not None}


__all__ = ["record_outcome_from_effect"]
