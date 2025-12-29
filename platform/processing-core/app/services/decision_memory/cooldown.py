from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.decision_memory import DecisionMemoryEffectLabel, DecisionMemoryEntityType
from app.services.decision_memory import defaults, repository


@dataclass(frozen=True)
class CooldownStatus:
    cooldown: bool
    reason: str | None
    recent_count: int
    failed_streak: int


def evaluate_cooldown(
    db: Session,
    *,
    entity_type: DecisionMemoryEntityType,
    entity_id: str,
    action_code: str,
    now: datetime | None = None,
) -> CooldownStatus:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=defaults.COOLDOWN_DAYS)
    outcomes = repository.list_recent_outcomes(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action_code=action_code,
        cutoff=cutoff,
    )
    recent_count = len(outcomes)
    failed_streak = _failed_streak(outcomes)
    if recent_count >= defaults.MAX_REPEAT and failed_streak >= defaults.MAX_FAILED_STREAK:
        reason = (
            f"Action tried {defaults.MAX_REPEAT} times in {defaults.COOLDOWN_DAYS} days with no improvement"
        )
        return CooldownStatus(cooldown=True, reason=reason, recent_count=recent_count, failed_streak=failed_streak)
    return CooldownStatus(cooldown=False, reason=None, recent_count=recent_count, failed_streak=failed_streak)


def _failed_streak(outcomes) -> int:
    streak = 0
    for outcome in outcomes:
        if outcome.effect_label in {DecisionMemoryEffectLabel.NO_CHANGE, DecisionMemoryEffectLabel.WORSE}:
            streak += 1
        else:
            break
    return streak


__all__ = ["CooldownStatus", "evaluate_cooldown"]
