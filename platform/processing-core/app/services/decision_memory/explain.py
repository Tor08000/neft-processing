from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.decision_memory import DecisionMemoryEntityType
from app.services.decision_memory import cooldown, repository
from app.services.fleet_decision_choice import defaults as decision_choice_defaults


def build_decision_memory_section(
    db: Session,
    *,
    entity_type: DecisionMemoryEntityType,
    entity_id: str,
    action_code: str | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    outcomes = repository.list_outcomes_for_entity(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    last_actions = [
        {
            "action": decision_choice_defaults.ACTION_LABELS.get(item.action_code, item.action_code),
            "action_code": item.action_code,
            "effect": item.effect_label.value,
            "measured_at": _format_ts(item.measured_at),
        }
        for item in outcomes
    ]
    payload: dict[str, Any] = {"last_actions": last_actions}
    if action_code:
        status = cooldown.evaluate_cooldown(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            action_code=action_code,
        )
        payload["cooldown"] = {
            "action": decision_choice_defaults.ACTION_LABELS.get(action_code, action_code),
            "action_code": action_code,
            "active": status.cooldown,
            "reason": status.reason,
        }
    return payload


def _format_ts(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


__all__ = ["build_decision_memory_section"]
