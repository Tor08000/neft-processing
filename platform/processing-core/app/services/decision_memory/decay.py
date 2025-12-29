from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.decision_memory import DecisionOutcome
from app.services.decision_memory import defaults


@dataclass(frozen=True)
class WeightedOutcomeStats:
    weighted_success: float
    weighted_applied: float


def decay_weight(*, age_days: float, half_life_days: int | float) -> float:
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (age_days / half_life_days)


def outcome_age_days(outcome: DecisionOutcome, *, now: datetime) -> float:
    base_time = outcome.measured_at or outcome.applied_at
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)
    return max((now - base_time).total_seconds() / 86400, 0.0)


def compute_weighted_stats(
    outcomes: list[DecisionOutcome],
    *,
    now: datetime | None = None,
    half_life_days: int | float = defaults.HALF_LIFE_DAYS,
) -> WeightedOutcomeStats:
    now = now or datetime.now(timezone.utc)
    weighted_success = 0.0
    weighted_applied = 0.0
    for outcome in outcomes:
        age_days = outcome_age_days(outcome, now=now)
        weight = decay_weight(age_days=age_days, half_life_days=half_life_days)
        weighted_applied += weight
        if outcome.effect_label.value == "IMPROVED":
            weighted_success += weight
    return WeightedOutcomeStats(weighted_success=weighted_success, weighted_applied=weighted_applied)


__all__ = ["WeightedOutcomeStats", "compute_weighted_stats", "decay_weight", "outcome_age_days"]
