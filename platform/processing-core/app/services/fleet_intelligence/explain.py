from __future__ import annotations

from app.models.fleet_intelligence import DriverBehaviorLevel, StationTrustLevel


def build_driver_explain(
    *,
    score: int,
    level: DriverBehaviorLevel,
    top_factors: list[dict],
) -> dict:
    return {
        "driver_behavior": {
            "score": score,
            "level": level.value,
            "top_factors": top_factors,
            "recommendation": "Review driver behavior; require route-linked refuels.",
        }
    }


def build_vehicle_explain(
    *,
    efficiency_score: int,
    baseline_ml_per_100km: float,
    actual_ml_per_100km: float,
    delta_pct: float,
) -> dict:
    return {
        "vehicle_efficiency": {
            "efficiency_score": efficiency_score,
            "baseline_ml_per_100km": baseline_ml_per_100km,
            "actual_ml_per_100km": actual_ml_per_100km,
            "delta_pct": delta_pct,
            "recommendation": "Monitor vehicle efficiency trend and investigate deviations.",
        }
    }


def build_vehicle_no_distance_explain() -> dict:
    return {
        "vehicle_efficiency": {
            "efficiency_score": None,
            "reason": "no distance data",
        }
    }


def build_station_explain(
    *,
    trust_score: int,
    level: StationTrustLevel,
    reasons: list[str],
) -> dict:
    return {
        "station_trust": {
            "trust_score": trust_score,
            "level": level.value,
            "reasons": reasons,
            "recommendation": "Review station activity and tighten controls if needed.",
        }
    }


__all__ = [
    "build_driver_explain",
    "build_vehicle_explain",
    "build_vehicle_no_distance_explain",
    "build_station_explain",
]
