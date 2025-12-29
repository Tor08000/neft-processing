from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.fleet_intelligence import FITrendLabel
from app.services.fuel_intelligence import overlay


def build_fuel_insights(
    db: Session,
    *,
    tenant_id: int,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
    fraud_signals: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    insights = _build_fuel_recommendations(fraud_signals)
    if not insights:
        return []
    enriched = overlay.apply_trend_overlay(
        db,
        insights=insights,
        tenant_id=tenant_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        station_id=station_id,
    )
    for insight in enriched:
        labels = insight.pop("_trend_labels", [])
        if _has_label(labels, FITrendLabel.DEGRADING):
            if insight.get("severity") == "INFO":
                insight["severity"] = "WARNING"
            insight["trend_message"] = build_fuel_trend_message(FITrendLabel.DEGRADING, days=14)
        elif _all_label(labels, FITrendLabel.STABLE):
            insight["trend_message"] = build_fuel_trend_message(FITrendLabel.STABLE, days=14)
    return enriched


def build_fuel_trend_message(label: FITrendLabel, *, days: int) -> str:
    if label == FITrendLabel.DEGRADING:
        return f"Ухудшается последние {days} дней"
    if label == FITrendLabel.STABLE:
        return "Стабильно"
    return "Недостаточно данных"


def _build_fuel_recommendations(fraud_signals: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not fraud_signals:
        return []
    recommendations: dict[str, dict[str, Any]] = {}
    for signal in fraud_signals:
        signal_type = signal.get("type")
        if signal_type in {"DRIVER_VEHICLE_MISMATCH"}:
            recommendations.setdefault(
                "DRIVER_FUEL_MISMATCH",
                {
                    "code": "DRIVER_FUEL_MISMATCH",
                    "title": "Driver–fuel mismatch",
                    "recommendation": "Проверьте соответствие водителя, карты и транзакции.",
                    "severity": "INFO",
                },
            )
        if signal_type in {"ROUTE_DEVIATION_BEFORE_FUEL", "FUEL_OFF_ROUTE_STRONG", "FUEL_STOP_MISMATCH_STRONG"}:
            recommendations.setdefault(
                "ROUTE_FUEL_MISMATCH",
                {
                    "code": "ROUTE_FUEL_MISMATCH",
                    "title": "Route–fuel mismatch",
                    "recommendation": "Сверьте заправку с маршрутом и типом остановки.",
                    "severity": "INFO",
                },
            )
        if signal_type in {"STATION_OUTLIER_CLUSTER", "MULTI_CARD_SAME_STATION_BURST"}:
            recommendations.setdefault(
                "STATION_FUEL_SPIKE",
                {
                    "code": "STATION_FUEL_SPIKE",
                    "title": "Station fuel spike",
                    "recommendation": "Проверьте всплеск активности на станции.",
                    "severity": "INFO",
                },
            )
    return list(recommendations.values())


def _has_label(labels: list[str], label: FITrendLabel) -> bool:
    return any(item == label.value for item in labels)


def _all_label(labels: list[str], label: FITrendLabel) -> bool:
    return labels and all(item == label.value for item in labels)


__all__ = ["build_fuel_insights", "build_fuel_trend_message"]
