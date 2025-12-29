from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import pow
from typing import Iterable

from app.models.fleet_intelligence_actions import FIActionCode, FIActionEffect, FIActionEffectLabel
from app.services.fleet_intelligence.control import defaults, repository


IMPROVED_FLAG = 1
NO_CHANGE_FLAG = 0
WORSE_FLAG = 0


def compute_action_confidence(
    db,
    *,
    action_code: FIActionCode,
    window_days: int = defaults.CONFIDENCE_WINDOW_DAYS,
    half_life_days: int = defaults.CONF_HALF_LIFE_DAYS,
    now: datetime | None = None,
) -> float:
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    effects = repository.list_action_effects_for_action_code(db, action_code=action_code, cutoff=cutoff)
    return compute_weighted_confidence(effects, now=now, half_life_days=half_life_days)


def compute_weighted_confidence(
    effects: Iterable[FIActionEffect],
    *,
    now: datetime,
    half_life_days: int,
) -> float:
    total_weight = 0.0
    improved_weight = 0.0
    for effect in effects:
        measured_at = effect.measured_at or now
        if measured_at.tzinfo is None:
            measured_at = measured_at.replace(tzinfo=timezone.utc)
        age_days = max((now - measured_at).total_seconds() / 86400.0, 0.0)
        weight = pow(0.5, age_days / float(half_life_days))
        total_weight += weight
        improved_weight += weight * _label_to_flag(effect.effect_label)
    if total_weight <= 0:
        return 0.0
    return improved_weight / total_weight


def _label_to_flag(label: FIActionEffectLabel) -> int:
    if label == FIActionEffectLabel.IMPROVED:
        return IMPROVED_FLAG
    if label == FIActionEffectLabel.NO_CHANGE:
        return NO_CHANGE_FLAG
    return WORSE_FLAG


__all__ = ["compute_action_confidence", "compute_weighted_confidence"]
