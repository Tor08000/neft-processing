from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InsightThresholds:
    degrading_days_medium: int = 2
    degrading_days_high: int = 5
    driver_score_high: int = 75
    driver_score_critical: int = 90
    station_score_high: int = 45
    station_score_critical: int = 30
    vehicle_efficiency_high: int = 40
    vehicle_efficiency_critical: int = 25


@dataclass(frozen=True)
class EffectThresholds:
    driver_score_improve_delta: int = 10
    driver_score_worse_delta: int = 10
    vehicle_efficiency_improve_delta: int = 10
    vehicle_efficiency_worse_delta: int = 10
    station_trust_improve_delta: int = 10
    station_trust_worse_delta: int = 10


INSIGHT_THRESHOLDS = InsightThresholds()
EFFECT_THRESHOLDS = EffectThresholds()
CONFIDENCE_WINDOW_DAYS = 90
CONF_HALF_LIFE_DAYS = 30

__all__ = [
    "INSIGHT_THRESHOLDS",
    "EFFECT_THRESHOLDS",
    "CONFIDENCE_WINDOW_DAYS",
    "CONF_HALF_LIFE_DAYS",
    "InsightThresholds",
    "EffectThresholds",
]
