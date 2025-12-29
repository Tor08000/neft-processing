from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.fleet_intelligence import FITrendEntityType, FITrendLabel, FITrendMetric, FITrendWindow
from app.models.logistics import LogisticsOrder, LogisticsTrackingEvent
from app.services.fleet_intelligence import repository as fi_repository


@dataclass(frozen=True)
class LogisticsRiskContext:
    order_id: str
    client_id: str
    vehicle_id: str | None
    driver_id: str | None
    status: str
    last_event_type: str | None
    last_event_ts: datetime | None
    driver_score_level: str | None
    station_trust_level: str | None
    vehicle_efficiency_delta_pct: float | None
    fleet_trend_driver_label: str | None
    fleet_trend_station_label: str | None
    fleet_trend_vehicle_label: str | None
    risk_hints: list[str]


def build_risk_context(
    *,
    order: LogisticsOrder,
    last_event: LogisticsTrackingEvent | None = None,
    db: Session | None = None,
) -> LogisticsRiskContext:
    session = db or order._sa_instance_state.session
    fleet_scores = fi_repository.latest_scores_for_ids(
        db=session,
        tenant_id=order.tenant_id,
        client_id=order.client_id,
        driver_id=str(order.driver_id) if order.driver_id else None,
        vehicle_id=str(order.vehicle_id) if order.vehicle_id else None,
        station_id=None,
        window_days=7,
    )
    fleet_trends = {
        "driver": fi_repository.get_latest_trend_snapshot(
            session,
            tenant_id=order.tenant_id,
            entity_type=FITrendEntityType.DRIVER,
            entity_id=str(order.driver_id),
            metric=FITrendMetric.DRIVER_BEHAVIOR_SCORE,
            window=FITrendWindow.D7,
        )
        if order.driver_id
        else None,
        "vehicle": fi_repository.get_latest_trend_snapshot(
            session,
            tenant_id=order.tenant_id,
            entity_type=FITrendEntityType.VEHICLE,
            entity_id=str(order.vehicle_id),
            metric=FITrendMetric.VEHICLE_EFFICIENCY_DELTA_PCT,
            window=FITrendWindow.ROLLING,
        )
        if order.vehicle_id
        else None,
    }
    risk_hints = []
    if any(trend and trend.label == FITrendLabel.DEGRADING for trend in fleet_trends.values()):
        risk_hints.append("fleet_trend_degrading")
    return LogisticsRiskContext(
        order_id=str(order.id),
        client_id=order.client_id,
        vehicle_id=str(order.vehicle_id) if order.vehicle_id else None,
        driver_id=str(order.driver_id) if order.driver_id else None,
        status=order.status.value,
        last_event_type=last_event.event_type.value if last_event else None,
        last_event_ts=last_event.ts if last_event else None,
        driver_score_level=fleet_scores.get("driver").level.value if fleet_scores.get("driver") else None,
        station_trust_level=None,
        vehicle_efficiency_delta_pct=fleet_scores.get("vehicle").delta_pct if fleet_scores.get("vehicle") else None,
        fleet_trend_driver_label=fleet_trends["driver"].label.value if fleet_trends.get("driver") else None,
        fleet_trend_station_label=None,
        fleet_trend_vehicle_label=fleet_trends["vehicle"].label.value if fleet_trends.get("vehicle") else None,
        risk_hints=risk_hints,
    )


__all__ = ["LogisticsRiskContext", "build_risk_context"]
