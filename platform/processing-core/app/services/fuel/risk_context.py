from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func

from app.models.fleet import FleetDriver, FleetVehicle
from app.models.fuel import FuelCard, FuelStation, FuelTransaction, FuelTransactionStatus, FuelType
from app.models.fleet_intelligence import FITrendEntityType, FITrendLabel, FITrendMetric, FITrendWindow
from app.schemas.fuel import DeclineCode
from app.services.decision import DecisionAction, DecisionContext
from app.services.fuel import fraud, repository
from app.services.logistics import repository as logistics_repository
from app.models.logistics import LogisticsNavigatorExplainType
from app.services.fleet_intelligence import repository as fi_repository

MSK_TZ = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True)
class RiskContextResult:
    decision_context: DecisionContext
    decline_code: DeclineCode | None
    factors: list[str]


def build_risk_context_for_fuel_tx(
    *,
    tenant_id: int,
    client_id: str,
    card: FuelCard,
    station: FuelStation,
    vehicle: FleetVehicle | None,
    driver: FleetDriver | None,
    fuel_type: FuelType,
    amount_minor: int,
    volume_ml: int,
    occurred_at: datetime,
    currency: str,
    subject_id: str,
    policy_override_id: str | None,
    thresholds_override: dict | None,
    policy_source: str,
    logistics_window_hours: int | None,
    severity_multiplier: float | None,
    db,
) -> RiskContextResult:
    station_risk_zone = (station.risk_zone or "").upper() or None
    station_risk_tags: list[str] = []
    if station_risk_zone == "YELLOW":
        station_risk_tags.append("STATION_RISK_YELLOW")
    elif station_risk_zone == "RED":
        station_risk_tags.append("STATION_RISK_RED")

    local_ts = occurred_at.astimezone(MSK_TZ)
    hour_of_day = local_ts.hour
    last_hour = occurred_at - timedelta(hours=1)
    last_day = occurred_at - timedelta(hours=24)

    tx_count_1h = repository.list_fuel_tx_count(db, card_id=str(card.id), start_at=last_hour, end_at=occurred_at)
    tx_count_24h = repository.list_fuel_tx_count(db, card_id=str(card.id), start_at=last_day, end_at=occurred_at)

    totals_24h = (
        db.query(
            func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0),
            func.coalesce(func.sum(FuelTransaction.volume_ml), 0),
        )
        .filter(FuelTransaction.card_id == card.id)
        .filter(
            FuelTransaction.status.in_(
                [
                    FuelTransactionStatus.AUTHORIZED,
                    FuelTransactionStatus.REVIEW_REQUIRED,
                    FuelTransactionStatus.SETTLED,
                ]
            )
        )
        .filter(FuelTransaction.occurred_at >= last_day)
        .filter(FuelTransaction.occurred_at <= occurred_at)
        .one()
    )
    total_amount_24h = int(totals_24h[0] or 0)
    total_volume_24h = int(totals_24h[1] or 0)

    totals_1h = (
        db.query(
            func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0),
        )
        .filter(FuelTransaction.card_id == card.id)
        .filter(
            FuelTransaction.status.in_(
                [
                    FuelTransactionStatus.AUTHORIZED,
                    FuelTransactionStatus.REVIEW_REQUIRED,
                    FuelTransactionStatus.SETTLED,
                ]
            )
        )
        .filter(FuelTransaction.occurred_at >= last_hour)
        .filter(FuelTransaction.occurred_at <= occurred_at)
        .one()
    )
    total_amount_1h = int(totals_1h[0] or 0)

    factors: list[str] = []
    decline_code: DeclineCode | None = None
    if vehicle and vehicle.tank_capacity_liters:
        capacity_ml = int(Decimal(vehicle.tank_capacity_liters) * Decimal("1000"))
        if volume_ml > int(capacity_ml * 1.2):
            factors.append("tank_sanity_exceeded")
            decline_code = DeclineCode.RISK_BLOCK
    if tx_count_1h >= 5 or tx_count_24h >= 20:
        factors.append("velocity_spike")
        decline_code = decline_code or DeclineCode.RISK_BLOCK

    logistics_signals = _summarize_logistics_signals(
        db,
        client_id=client_id,
        vehicle_id=str(vehicle.id) if vehicle else None,
        driver_id=str(driver.id) if driver else None,
        occurred_at=occurred_at,
        window_hours=logistics_window_hours,
        severity_multiplier=severity_multiplier,
    )
    navigator_signals = _navigator_signals(db, order_id=logistics_signals.get("order_id"))
    fraud_candidates = fraud.evaluate_fraud_signals(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        card=card,
        station=station,
        vehicle_id=str(vehicle.id) if vehicle else None,
        driver_id=str(driver.id) if driver else None,
        occurred_at=occurred_at,
        volume_ml=volume_ml,
        amount_minor=amount_minor,
        request_vehicle_plate=None,
        request_driver_id=None,
        include_current=True,
    )
    fraud_summary = fraud.summarize_fraud_signals(
        db,
        client_id=client_id,
        vehicle_id=str(vehicle.id) if vehicle else None,
        driver_id=str(driver.id) if driver else None,
        station_id=str(station.id),
        occurred_at=occurred_at,
        pending_signals=fraud_candidates,
    )
    fleet_scores = fi_repository.latest_scores_for_ids(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        driver_id=str(driver.id) if driver else None,
        vehicle_id=str(vehicle.id) if vehicle else None,
        station_id=str(station.id),
        window_days=7,
    )
    fleet_trends = {
        "driver": fi_repository.get_latest_trend_snapshot(
            db,
            tenant_id=tenant_id,
            entity_type=FITrendEntityType.DRIVER,
            entity_id=str(driver.id),
            metric=FITrendMetric.DRIVER_BEHAVIOR_SCORE,
            window=FITrendWindow.D7,
        )
        if driver
        else None,
        "station": fi_repository.get_latest_trend_snapshot(
            db,
            tenant_id=tenant_id,
            entity_type=FITrendEntityType.STATION,
            entity_id=str(station.id),
            metric=FITrendMetric.STATION_TRUST_SCORE,
            window=FITrendWindow.D30,
        ),
        "vehicle": fi_repository.get_latest_trend_snapshot(
            db,
            tenant_id=tenant_id,
            entity_type=FITrendEntityType.VEHICLE,
            entity_id=str(vehicle.id),
            metric=FITrendMetric.VEHICLE_EFFICIENCY_DELTA_PCT,
            window=FITrendWindow.ROLLING,
        )
        if vehicle
        else None,
    }
    risk_hints = []
    if any(trend and trend.label == FITrendLabel.DEGRADING for trend in fleet_trends.values()):
        risk_hints.append("fleet_trend_degrading")
    metadata = {
        "card_status": card.status.value,
        "station_id": str(station.id),
        "network_id": str(station.network_id),
        "fuel_type": fuel_type.value,
        "volume_ml": volume_ml,
        "volume_liters": float(Decimal(volume_ml) / Decimal("1000")),
        "amount_total_minor": amount_minor,
        "tx_count_1h": int(tx_count_1h),
        "tx_count_24h": int(tx_count_24h),
        "amount_sum_1h": total_amount_1h,
        "amount_sum_24h": total_amount_24h,
        "total_amount_24h": total_amount_24h,
        "total_volume_24h": total_volume_24h,
        "hour_of_day": hour_of_day,
        "vehicle_id": str(vehicle.id) if vehicle else None,
        "driver_id": str(driver.id) if driver else None,
        "factors": factors,
        "subject_id": subject_id,
        "policy_override_id": policy_override_id,
        "thresholds_override": thresholds_override,
        "policy_source": policy_source,
        "logistics_signals": logistics_signals,
        "logistics_off_route_summary": _summarize_off_route_events(
            db,
            order_id=logistics_signals.get("order_id"),
            occurred_at=occurred_at,
            window_hours=logistics_window_hours,
        ),
        "route_deviation_score": navigator_signals.get("route_deviation_score"),
        "eta_overrun_pct": navigator_signals.get("eta_overrun_pct"),
        **fraud_summary,
        "driver_score_level": fleet_scores.get("driver").level.value if fleet_scores.get("driver") else None,
        "station_trust_level": fleet_scores.get("station").level.value if fleet_scores.get("station") else None,
        "vehicle_efficiency_delta_pct": fleet_scores.get("vehicle").delta_pct if fleet_scores.get("vehicle") else None,
        "fleet_trend_driver_label": fleet_trends["driver"].label.value if fleet_trends.get("driver") else None,
        "fleet_trend_station_label": fleet_trends["station"].label.value if fleet_trends.get("station") else None,
        "fleet_trend_vehicle_label": fleet_trends["vehicle"].label.value if fleet_trends.get("vehicle") else None,
        "risk_hints": risk_hints,
        "station_risk_zone": station_risk_zone,
        "risk_tags": station_risk_tags,
    }
    if fraud_summary.get("has_strong_off_route") and fraud_summary.get("max_signal_severity_24h"):
        metadata["risk_score"] = max(metadata.get("risk_score", 0), int(fraud_summary["max_signal_severity_24h"]))
    decision_context = DecisionContext(
        tenant_id=tenant_id,
        client_id=client_id,
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=amount_minor,
        currency=currency,
        payment_method="FUEL_CARD",
        history={},
        metadata=metadata,
    )

    return RiskContextResult(decision_context=decision_context, decline_code=decline_code, factors=factors)


def _summarize_logistics_signals(
    db,
    *,
    client_id: str,
    vehicle_id: str | None,
    driver_id: str | None,
    occurred_at: datetime,
    window_hours: int | None,
    severity_multiplier: float | None,
) -> dict:
    window = window_hours or 24
    multiplier = severity_multiplier or 1.0
    since = occurred_at - timedelta(hours=window)
    signals = logistics_repository.list_recent_risk_signals(
        db,
        client_id=client_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        since=since,
    )
    summary: dict[str, dict] = {"order_id": None}
    for signal in signals:
        summary["order_id"] = str(signal.order_id)
        entry = summary.setdefault(
            signal.signal_type.value,
            {"count": 0, "max_severity": 0, "latest_ts": None},
        )
        entry["count"] += 1
        adjusted_severity = float(signal.severity) * multiplier
        entry["max_severity"] = max(entry["max_severity"], adjusted_severity)
        if entry["latest_ts"] is None or signal.ts > entry["latest_ts"]:
            entry["latest_ts"] = signal.ts.isoformat()
    return summary


def _summarize_off_route_events(
    db,
    *,
    order_id: str | None,
    occurred_at: datetime,
    window_hours: int | None,
) -> dict | None:
    if not order_id:
        return None
    window = window_hours or 24
    since = occurred_at - timedelta(hours=window)
    events = logistics_repository.list_recent_deviation_events(db, order_id=order_id, since=since)
    off_route = [event for event in events if event.event_type.value == "OFF_ROUTE"]
    if not off_route:
        return {"count": 0, "max_severity": 0, "last_ts": None}
    max_severity = max(
        {"LOW": 30, "MEDIUM": 60, "HIGH": 80}.get(event.severity.value, 0) for event in off_route
    )
    last_ts = max(event.ts for event in off_route).isoformat()
    return {"count": len(off_route), "max_severity": max_severity, "last_ts": last_ts}


def _navigator_signals(db, *, order_id: str | None) -> dict:
    # Risk context consumes the same local navigator evidence contour.
    # These signals should not be interpreted as processing-core owning external routing transport.
    if not order_id:
        return {"route_deviation_score": None, "eta_overrun_pct": None}
    route = logistics_repository.get_active_route(db, order_id=order_id)
    if not route:
        return {"route_deviation_score": None, "eta_overrun_pct": None}
    snapshot = logistics_repository.get_latest_route_snapshot(db, route_id=str(route.id))
    if not snapshot:
        return {"route_deviation_score": None, "eta_overrun_pct": None}

    explains = logistics_repository.list_navigator_explains(
        db,
        route_snapshot_id=str(snapshot.id),
        explain_type=LogisticsNavigatorExplainType.DEVIATION,
        limit=1,
    )
    deviation_score = explains[0].payload.get("score") if explains else None

    eta_overrun_pct = None
    if snapshot.eta_minutes is not None and route.planned_duration_minutes:
        delta = snapshot.eta_minutes - route.planned_duration_minutes
        if route.planned_duration_minutes > 0 and delta > 0:
            eta_overrun_pct = round((delta / route.planned_duration_minutes) * 100, 2)

    return {
        "route_deviation_score": deviation_score,
        "eta_overrun_pct": eta_overrun_pct,
    }
