from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.fleet_intelligence import FITrendEntityType, FITrendLabel, FITrendMetric, FITrendWindow
from app.services.fleet_intelligence import repository as fi_repository
def apply_trend_overlay(
    db: Session,
    *,
    insights: list[dict[str, Any]],
    tenant_id: int,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
) -> list[dict[str, Any]]:
    for insight in insights:
        code = insight.get("code")
        overlay: dict[str, Any] = {}
        labels: list[FITrendLabel] = []
        if code == "DRIVER_FUEL_MISMATCH" and driver_id:
            driver_trend = _load_driver_trend(db, tenant_id=tenant_id, driver_id=driver_id)
            if driver_trend:
                overlay["driver"] = _serialize_trend(driver_trend, window_days=7)
                labels.append(driver_trend.label)
        if code == "ROUTE_FUEL_MISMATCH":
            if driver_id:
                driver_trend = _load_driver_trend(db, tenant_id=tenant_id, driver_id=driver_id)
                if driver_trend:
                    overlay["driver"] = _serialize_trend(driver_trend, window_days=7)
                    labels.append(driver_trend.label)
            if vehicle_id:
                vehicle_trend = _load_vehicle_trend(db, tenant_id=tenant_id, vehicle_id=vehicle_id)
                if vehicle_trend:
                    overlay["vehicle"] = _serialize_trend(vehicle_trend, window_days=7)
                    labels.append(vehicle_trend.label)
        if code == "STATION_FUEL_SPIKE" and station_id:
            station_trend = _load_station_trend(db, tenant_id=tenant_id, station_id=station_id)
            if station_trend:
                overlay["station"] = _serialize_trend(station_trend, window_days=30)
                labels.append(station_trend.label)
        if not overlay:
            continue
        insight["trend_overlay"] = overlay
        insight["_trend_labels"] = [label.value for label in labels]
    return insights


def _serialize_trend(trend, *, window_days: int) -> dict[str, Any]:
    payload = {"label": trend.label.value}
    delta_key = f"delta_{window_days}d"
    payload[delta_key] = trend.delta
    return payload


def _load_driver_trend(db: Session, *, tenant_id: int, driver_id: str):
    return fi_repository.get_latest_trend_snapshot(
        db,
        tenant_id=tenant_id,
        entity_type=FITrendEntityType.DRIVER,
        entity_id=driver_id,
        metric=FITrendMetric.DRIVER_BEHAVIOR_SCORE,
        window=FITrendWindow.D7,
    )


def _load_vehicle_trend(db: Session, *, tenant_id: int, vehicle_id: str):
    return fi_repository.get_latest_trend_snapshot(
        db,
        tenant_id=tenant_id,
        entity_type=FITrendEntityType.VEHICLE,
        entity_id=vehicle_id,
        metric=FITrendMetric.VEHICLE_EFFICIENCY_DELTA_PCT,
        window=FITrendWindow.ROLLING,
    )


def _load_station_trend(db: Session, *, tenant_id: int, station_id: str):
    return fi_repository.get_latest_trend_snapshot(
        db,
        tenant_id=tenant_id,
        entity_type=FITrendEntityType.STATION,
        entity_id=station_id,
        metric=FITrendMetric.STATION_TRUST_SCORE,
        window=FITrendWindow.D30,
    )


__all__ = ["apply_trend_overlay"]
