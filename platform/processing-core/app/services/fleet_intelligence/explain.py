from __future__ import annotations

from app.models.fleet_intelligence import DriverBehaviorLevel, FITrendLabel, StationTrustLevel


_DRIVER_FACTOR_LABELS = {
    "off_route_fuel_count": "Отклонения от маршрута",
    "night_fuel_tx_count": "Ночные заправки",
    "route_deviation_count": "Отклонения от маршрута",
    "risk_block_count": "Блокировки",
    "review_required_count": "Требования проверки",
    "tx_count": "Транзакции",
}


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


def build_driver_summary(*, top_factors: list[dict]) -> str:
    if not top_factors:
        return "Недостаточно данных по поведению водителя."
    parts = []
    for factor in top_factors:
        label = _DRIVER_FACTOR_LABELS.get(factor.get("factor"), str(factor.get("factor")))
        value = factor.get("value")
        if isinstance(value, (int, float)):
            value = int(round(value))
        parts.append(f"{label}: {value}")
    return ", ".join(parts)


def build_station_summary(*, level: StationTrustLevel, reasons: list[str]) -> str:
    level_label = "watchlist" if level == StationTrustLevel.WATCHLIST else "blacklist"
    if reasons:
        reasons_text = ", ".join(reasons)
        return f"Станция в {level_label}: {reasons_text}"
    return f"Станция в {level_label}."


def build_vehicle_summary(*, delta_pct: float | None, window_days: int | None) -> str:
    if delta_pct is None:
        return "Нет данных по пробегу."
    delta_percent = int(round(delta_pct * 100))
    sign = "+" if delta_percent >= 0 else ""
    days_label = f"{window_days} дней" if window_days else "последний период"
    return f"Расход {sign}{delta_percent}% к базовому за {days_label}"


def build_driver_trend_explain(*, top_factors: list[dict]) -> dict:
    return {"top_factors": top_factors[:2]}


def build_station_trend_explain(*, reasons: list[str]) -> dict:
    return {"reasons": reasons[:2]}


def build_vehicle_trend_explain(
    *,
    delta_pct: float | None,
    baseline_ml_per_100km: float | None,
    actual_ml_per_100km: float | None,
) -> dict:
    return {
        "delta_pct": delta_pct,
        "baseline_ml_per_100km": baseline_ml_per_100km,
        "actual_ml_per_100km": actual_ml_per_100km,
    }


def build_trend_message(*, label: FITrendLabel, days: int | None) -> str:
    templates = {
        FITrendLabel.DEGRADING: "Ситуация ухудшается последние {days} дней",
        FITrendLabel.IMPROVING: "Ситуация улучшается последние {days} дней",
        FITrendLabel.STABLE: "Ситуация стабильна",
    }
    template = templates.get(label, "Недостаточно данных по тренду.")
    if label in {FITrendLabel.DEGRADING, FITrendLabel.IMPROVING} and days:
        return template.format(days=days)
    return template


__all__ = [
    "build_driver_explain",
    "build_vehicle_explain",
    "build_vehicle_no_distance_explain",
    "build_station_explain",
    "build_driver_summary",
    "build_station_summary",
    "build_vehicle_summary",
    "build_driver_trend_explain",
    "build_station_trend_explain",
    "build_vehicle_trend_explain",
    "build_trend_message",
]
