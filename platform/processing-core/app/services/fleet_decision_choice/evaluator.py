from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.fleet_decision_choice import defaults


@dataclass(frozen=True)
class ActionEffectStats:
    action_code: str
    insight_type: str
    window_days: int
    applied_count: int
    improved_count: int
    no_change_count: int
    worsened_count: int
    avg_effect_delta: float | None
    last_computed_at: datetime | None


@dataclass(frozen=True)
class ActionEvaluation:
    success_rate: float
    confidence_weight: float
    effect_strength: float


def evaluate_action(stats: ActionEffectStats, *, now: datetime | None = None) -> ActionEvaluation:
    now = now or datetime.now(timezone.utc)
    success_rate = _success_rate(stats)
    confidence_weight = _confidence_weight(stats, now=now)
    effect_strength = float(stats.avg_effect_delta or 0.0)
    return ActionEvaluation(
        success_rate=success_rate,
        confidence_weight=confidence_weight,
        effect_strength=effect_strength,
    )


def _success_rate(stats: ActionEffectStats) -> float:
    if stats.applied_count <= 0:
        return 0.0
    return stats.improved_count / stats.applied_count


def _confidence_weight(stats: ActionEffectStats, *, now: datetime) -> float:
    if stats.applied_count <= 0:
        return 0.0
    sample_factor = min(stats.applied_count / defaults.CONFIDENCE_SATURATION_COUNT, 1.0)
    recency_factor = _recency_factor(stats.last_computed_at, now=now)
    return max(0.0, min(1.0, sample_factor * recency_factor))


def _recency_factor(last_computed_at: datetime | None, *, now: datetime) -> float:
    if not last_computed_at:
        return 1.0
    if last_computed_at.tzinfo is None:
        last_computed_at = last_computed_at.replace(tzinfo=timezone.utc)
    delta_days = max((now - last_computed_at).total_seconds() / 86400, 0.0)
    if defaults.CONFIDENCE_HALF_LIFE_DAYS <= 0:
        return 1.0
    return 0.5 ** (delta_days / defaults.CONFIDENCE_HALF_LIFE_DAYS)


__all__ = ["ActionEffectStats", "ActionEvaluation", "evaluate_action"]
