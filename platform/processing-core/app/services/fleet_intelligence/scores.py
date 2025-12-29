from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable

from app.models.fleet_intelligence import DriverBehaviorLevel, StationTrustLevel
from app.services.fleet_intelligence.defaults import (
    DRIVER_SCORE_THRESHOLDS,
    DRIVER_SCORE_WEIGHTS,
    STATION_BURST_EVENTS_HIGH,
    STATION_DECLINE_RATE_HIGH,
    STATION_RISK_BLOCK_RATE_HIGH,
    STATION_VOLUME_DEVIATION_HIGH,
    VEHICLE_BASELINE_DAYS,
)


@dataclass(frozen=True)
class DriverScoreInputs:
    off_route_fuel_count: int
    night_fuel_tx_count: int
    route_deviation_count: int
    risk_block_count: int
    review_required_count: int
    tx_count: int


@dataclass(frozen=True)
class DriverScoreResult:
    score: int
    level: DriverBehaviorLevel
    contributions: dict[str, float]


@dataclass(frozen=True)
class VehicleEfficiencyInputs:
    window_days: int
    baseline_days: int
    baseline_ml_per_100km: float | None
    actual_ml_per_100km: float | None


@dataclass(frozen=True)
class VehicleEfficiencyResult:
    efficiency_score: int | None
    baseline_ml_per_100km: float | None
    actual_ml_per_100km: float | None
    delta_pct: float | None


@dataclass(frozen=True)
class StationTrustInputs:
    tx_count: int
    risk_block_count: int
    decline_count: int
    burst_events_count: int
    outlier_score: float | None
    avg_volume_ml: float | None
    network_avg_volume_ml: float | None


@dataclass(frozen=True)
class StationTrustResult:
    trust_score: int
    level: StationTrustLevel
    penalties: dict[str, float]


def compute_driver_behavior_score(inputs: DriverScoreInputs) -> DriverScoreResult:
    contributions = {
        "off_route_fuel_count": DRIVER_SCORE_WEIGHTS.off_route_fuel_count
        * _normalize(inputs.off_route_fuel_count, DRIVER_SCORE_THRESHOLDS.off_route_fuel_count),
        "night_fuel_tx_count": DRIVER_SCORE_WEIGHTS.night_fuel_tx_count
        * _normalize(inputs.night_fuel_tx_count, DRIVER_SCORE_THRESHOLDS.night_fuel_tx_count),
        "route_deviation_count": DRIVER_SCORE_WEIGHTS.route_deviation_count
        * _normalize(inputs.route_deviation_count, DRIVER_SCORE_THRESHOLDS.route_deviation_count),
        "risk_block_count": DRIVER_SCORE_WEIGHTS.risk_block_count
        * _normalize(inputs.risk_block_count, DRIVER_SCORE_THRESHOLDS.risk_block_count),
        "review_required_count": DRIVER_SCORE_WEIGHTS.review_required_count
        * _normalize(inputs.review_required_count, DRIVER_SCORE_THRESHOLDS.review_required_count),
        "tx_count": DRIVER_SCORE_WEIGHTS.tx_count
        * _normalize(inputs.tx_count, DRIVER_SCORE_THRESHOLDS.tx_count),
    }
    score = int(round(_clamp(sum(contributions.values()), 0, 100)))
    level = _driver_level(score)
    return DriverScoreResult(score=score, level=level, contributions=contributions)


def compute_vehicle_efficiency_score(
    *,
    window_days: int,
    daily_values: Iterable[float],
    baseline_values: Iterable[float],
    baseline_days: int = VEHICLE_BASELINE_DAYS,
) -> VehicleEfficiencyResult:
    actual_values = [value for value in daily_values if value is not None]
    if not actual_values:
        return VehicleEfficiencyResult(
            efficiency_score=None,
            baseline_ml_per_100km=None,
            actual_ml_per_100km=None,
            delta_pct=None,
        )
    baseline_candidates = [value for value in baseline_values if value is not None]
    baseline = median(baseline_candidates) if baseline_candidates else None
    actual = sum(actual_values) / len(actual_values)
    if baseline is None or baseline <= 0:
        return VehicleEfficiencyResult(
            efficiency_score=None,
            baseline_ml_per_100km=baseline,
            actual_ml_per_100km=actual,
            delta_pct=None,
        )
    delta_pct = (actual - baseline) / baseline
    efficiency_score = _vehicle_efficiency_score(delta_pct)
    return VehicleEfficiencyResult(
        efficiency_score=efficiency_score,
        baseline_ml_per_100km=baseline,
        actual_ml_per_100km=actual,
        delta_pct=delta_pct,
    )


def compute_station_trust_score(inputs: StationTrustInputs) -> StationTrustResult:
    tx_count = max(inputs.tx_count, 0)
    risk_block_rate = inputs.risk_block_count / tx_count if tx_count else 0.0
    decline_rate = inputs.decline_count / tx_count if tx_count else 0.0
    penalties: dict[str, float] = {}
    trust_score = 100.0

    if risk_block_rate >= STATION_RISK_BLOCK_RATE_HIGH:
        penalties["risk_block_rate"] = 30.0
        trust_score -= 30.0

    if decline_rate >= STATION_DECLINE_RATE_HIGH:
        penalties["decline_rate"] = 10.0
        trust_score -= 10.0

    if inputs.burst_events_count >= STATION_BURST_EVENTS_HIGH:
        penalties["burst_events"] = 20.0
        trust_score -= 20.0

    if inputs.outlier_score:
        penalties["outlier_score"] = float(inputs.outlier_score) * 0.3
        trust_score -= penalties["outlier_score"]

    volume_deviation = _volume_deviation(inputs.avg_volume_ml, inputs.network_avg_volume_ml)
    if volume_deviation is not None and volume_deviation >= STATION_VOLUME_DEVIATION_HIGH:
        penalties["avg_volume_deviation"] = 10.0
        trust_score -= 10.0

    trust_score = int(round(_clamp(trust_score, 0, 100)))
    level = _station_level(trust_score)
    return StationTrustResult(trust_score=trust_score, level=level, penalties=penalties)


def _normalize(value: int, threshold: int) -> float:
    if threshold <= 0:
        return 0.0
    return min(value / float(threshold), 1.0)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _driver_level(score: int) -> DriverBehaviorLevel:
    if score <= 25:
        return DriverBehaviorLevel.LOW
    if score <= 50:
        return DriverBehaviorLevel.MEDIUM
    if score <= 75:
        return DriverBehaviorLevel.HIGH
    return DriverBehaviorLevel.VERY_HIGH


def _station_level(score: int) -> StationTrustLevel:
    if score >= 80:
        return StationTrustLevel.TRUSTED
    if score >= 50:
        return StationTrustLevel.WATCHLIST
    return StationTrustLevel.BLACKLIST


def _vehicle_efficiency_score(delta_pct: float) -> int:
    if delta_pct <= 0:
        return 95
    if delta_pct <= 0.1:
        return 80
    if delta_pct <= 0.25:
        return 55
    return 20


def _volume_deviation(avg_volume_ml: float | None, network_avg_volume_ml: float | None) -> float | None:
    if avg_volume_ml is None or network_avg_volume_ml in (None, 0):
        return None
    return abs(avg_volume_ml - network_avg_volume_ml) / network_avg_volume_ml


__all__ = [
    "DriverScoreInputs",
    "DriverScoreResult",
    "VehicleEfficiencyInputs",
    "VehicleEfficiencyResult",
    "StationTrustInputs",
    "StationTrustResult",
    "compute_driver_behavior_score",
    "compute_vehicle_efficiency_score",
    "compute_station_trust_score",
]
