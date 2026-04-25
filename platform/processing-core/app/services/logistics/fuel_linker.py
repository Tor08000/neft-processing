from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.fuel import FuelStation, FuelTransaction
from app.models.logistics import (
    FuelRouteLink,
    LogisticsFuelRouteLinkType,
    LogisticsOrder,
    LogisticsRiskSignal,
    LogisticsRiskSignalType,
    LogisticsStopType,
)
from app.services.audit_service import RequestContext
from app.services.logistics import events, repository
from app.services.logistics.defaults import FUEL_LINK_DEFAULTS, RISK_SIGNAL_DEFAULTS
from app.services.logistics.metrics import metrics as logistics_metrics
from app.services.logistics.deviation import _haversine_m


@dataclass(frozen=True)
class FuelLinkResult:
    link: FuelRouteLink | None
    signal: LogisticsRiskSignal | None


def auto_link_for_order(
    db: Session,
    *,
    order: LogisticsOrder,
    request_ctx: RequestContext | None = None,
) -> list[FuelLinkResult]:
    if order.vehicle_id is None:
        return []
    transactions = (
        db.query(FuelTransaction)
        .filter(repository.id_equals(FuelTransaction.vehicle_id, order.vehicle_id))
        .filter(FuelTransaction.client_id == order.client_id)
        .order_by(FuelTransaction.occurred_at.desc())
        .limit(10)
        .all()
    )
    results: list[FuelLinkResult] = []
    for tx in transactions:
        results.append(auto_link_fuel_tx(db, transaction=tx, request_ctx=request_ctx))
    return results


def _now() -> datetime:
    return datetime.now(timezone.utc)


def auto_link_fuel_tx(
    db: Session,
    *,
    transaction: FuelTransaction,
    request_ctx: RequestContext | None = None,
) -> FuelLinkResult:
    existing = (
        db.query(FuelRouteLink)
        .filter(FuelRouteLink.fuel_tx_id == transaction.id)
        .one_or_none()
    )
    if existing:
        return FuelLinkResult(link=existing, signal=None)
    if transaction.vehicle_id is None:
        return FuelLinkResult(link=None, signal=None)

    order = (
        db.query(LogisticsOrder)
        .filter(repository.id_equals(LogisticsOrder.vehicle_id, transaction.vehicle_id))
        .filter(LogisticsOrder.client_id == transaction.client_id)
        .order_by(LogisticsOrder.created_at.desc())
        .first()
    )
    if not order:
        return FuelLinkResult(link=None, signal=None)

    route = repository.get_active_route(db, order_id=str(order.id))
    if not route:
        return FuelLinkResult(link=None, signal=None)

    constraint = repository.get_route_constraint(db, route_id=str(route.id))
    window_minutes = constraint.allowed_fuel_window_minutes if constraint else FUEL_LINK_DEFAULTS.allowed_fuel_window_minutes
    start_at = transaction.occurred_at - timedelta(minutes=window_minutes)
    end_at = transaction.occurred_at + timedelta(minutes=window_minutes)

    stops = repository.get_route_stops(db, route_id=str(route.id))
    nearby_stops = []
    for stop in stops:
        candidate_times = [stop.planned_arrival_at, stop.actual_arrival_at, stop.actual_departure_at]
        if any(timestamp and start_at <= timestamp <= end_at for timestamp in candidate_times):
            nearby_stops.append(stop)

    station = db.query(FuelStation).filter(FuelStation.id == transaction.station_id).one_or_none()
    station_lat = float(station.lat) if station and station.lat else None
    station_lon = float(station.lon) if station and station.lon else None

    matched_stop = None
    min_distance = None
    if station_lat is not None and station_lon is not None:
        for stop in nearby_stops:
            distance = _haversine_m(station_lat, station_lon, float(stop.lat), float(stop.lon))
            if min_distance is None or distance < min_distance:
                min_distance = distance
                matched_stop = stop

    if matched_stop is None and stops:
        nearest_by_time = sorted(
            stops,
            key=lambda stop: abs(
                int(
                    (transaction.occurred_at - (stop.planned_arrival_at or transaction.occurred_at)).total_seconds()
                    / 60
                )
            ),
        )
        matched_stop = nearest_by_time[0]

    if matched_stop and min_distance is None:
        time_delta = _time_delta_minutes(transaction.occurred_at, _preferred_stop_time(matched_stop))
        if time_delta is not None and time_delta > window_minutes:
            matched_stop = None

    max_stop_radius = constraint.max_stop_radius_m if constraint else FUEL_LINK_DEFAULTS.max_stop_radius_m
    max_stop_radius_high = FUEL_LINK_DEFAULTS.max_stop_radius_high_m

    if matched_stop and (min_distance is None or min_distance <= max_stop_radius_high):
        link = FuelRouteLink(
            fuel_tx_id=str(transaction.id),
            order_id=str(order.id),
            route_id=str(route.id),
            stop_id=str(matched_stop.id),
            link_type=LogisticsFuelRouteLinkType.AUTO_MATCH,
            distance_to_stop_m=int(min_distance) if min_distance is not None else None,
            time_delta_minutes=_time_delta_minutes(transaction.occurred_at, _preferred_stop_time(matched_stop)),
        )
        db.add(link)
        db.flush()
        link_id = str(link.id)
        db.commit()
        link = repository.refresh_by_id(db, link, FuelRouteLink, link_id)

        events.audit_event(
            db,
            event_type=events.LOGISTICS_FUEL_LINK_CREATED,
            entity_type="fuel_route_link",
            entity_id=str(link.id),
            payload={
                "order_id": str(order.id),
                "fuel_tx_id": str(transaction.id),
                "stop_id": str(matched_stop.id),
            },
            request_ctx=request_ctx,
        )
        events.register_fuel_link_node(
            db,
            tenant_id=order.tenant_id,
            fuel_tx_id=str(transaction.id),
            link_id=str(link.id),
            stop_id=str(matched_stop.id),
            request_ctx=request_ctx,
        )

        if min_distance is not None and min_distance > max_stop_radius:
            signal = _emit_signal(
                db,
                order=order,
                signal_type=LogisticsRiskSignalType.FUEL_STOP_MISMATCH,
                severity=RISK_SIGNAL_DEFAULTS.fuel_stop_mismatch_severity,
                ts=_now(),
                explain=_build_explain(
                    signal_type="FUEL_STOP_MISMATCH",
                    route_id=str(route.id),
                    stop_candidates=len(nearby_stops),
                    distance_to_nearest_stop_m=int(min_distance),
                    time_delta_minutes=_time_delta_minutes(transaction.occurred_at, _preferred_stop_time(matched_stop)),
                    constraints=_constraint_payload(constraint),
                    recommendation="Verify fuel location against route stop",
                ),
                request_ctx=request_ctx,
            )
            logistics_metrics.inc("logistics_fuel_off_route_total")
            return FuelLinkResult(link=link, signal=signal)

        if matched_stop.stop_type != LogisticsStopType.FUEL:
            signal = _emit_signal(
                db,
                order=order,
                signal_type=LogisticsRiskSignalType.FUEL_STOP_MISMATCH,
                severity=RISK_SIGNAL_DEFAULTS.fuel_stop_mismatch_severity,
                ts=_now(),
                explain=_build_explain(
                    signal_type="FUEL_STOP_MISMATCH",
                    route_id=str(route.id),
                    stop_candidates=len(nearby_stops),
                    distance_to_nearest_stop_m=int(min_distance) if min_distance is not None else None,
                    time_delta_minutes=_time_delta_minutes(transaction.occurred_at, _preferred_stop_time(matched_stop)),
                    constraints=_constraint_payload(constraint),
                    recommendation="Check stop type vs fuel transaction",
                ),
                request_ctx=request_ctx,
            )
            logistics_metrics.inc("logistics_fuel_off_route_total")
            return FuelLinkResult(link=link, signal=signal)

        return FuelLinkResult(link=link, signal=None)

    signal = _emit_signal(
        db,
        order=order,
        signal_type=LogisticsRiskSignalType.FUEL_OFF_ROUTE,
        severity=RISK_SIGNAL_DEFAULTS.fuel_off_route_severity,
        ts=_now(),
        explain=_build_explain(
            signal_type="FUEL_OFF_ROUTE",
            route_id=str(route.id),
            stop_candidates=len(nearby_stops),
            distance_to_nearest_stop_m=int(min_distance) if min_distance is not None else None,
            time_delta_minutes=None,
            constraints=_constraint_payload(constraint),
            recommendation="Check driver activity or station legitimacy",
        ),
        request_ctx=request_ctx,
    )
    logistics_metrics.inc("logistics_fuel_off_route_total")
    return FuelLinkResult(link=None, signal=signal)


def _time_delta_minutes(occurred_at: datetime, planned_at: datetime | None) -> int | None:
    if planned_at is None:
        return None
    return int(abs((occurred_at - planned_at).total_seconds() / 60))


def _preferred_stop_time(stop) -> datetime | None:
    return stop.actual_arrival_at or stop.actual_departure_at or stop.planned_arrival_at


def _emit_signal(
    db: Session,
    *,
    order: LogisticsOrder,
    signal_type: LogisticsRiskSignalType,
    severity: int,
    ts: datetime,
    explain: dict,
    request_ctx: RequestContext | None,
) -> LogisticsRiskSignal:
    signal = LogisticsRiskSignal(
        tenant_id=order.tenant_id,
        client_id=order.client_id,
        order_id=str(order.id),
        vehicle_id=str(order.vehicle_id) if order.vehicle_id else None,
        driver_id=str(order.driver_id) if order.driver_id else None,
        signal_type=signal_type,
        severity=severity,
        ts=ts,
        explain=explain,
    )
    db.add(signal)
    db.flush()
    signal_id = str(signal.id)
    db.commit()
    signal = repository.refresh_by_id(db, signal, LogisticsRiskSignal, signal_id)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_RISK_SIGNAL_EMITTED,
        entity_type="logistics_risk_signal",
        entity_id=str(signal.id),
        payload={"order_id": str(order.id), "signal_type": signal.signal_type.value, "severity": severity},
        request_ctx=request_ctx,
    )
    events.register_risk_signal_node(
        db,
        tenant_id=order.tenant_id,
        order_id=str(order.id),
        signal_id=str(signal.id),
        request_ctx=request_ctx,
    )
    return signal


def _constraint_payload(constraint) -> dict:
    return {
        "max_stop_radius_m": constraint.max_stop_radius_m if constraint else FUEL_LINK_DEFAULTS.max_stop_radius_m,
        "allowed_fuel_window_minutes": constraint.allowed_fuel_window_minutes
        if constraint
        else FUEL_LINK_DEFAULTS.allowed_fuel_window_minutes,
    }


def _build_explain(
    *,
    signal_type: str,
    route_id: str | None,
    stop_candidates: int,
    distance_to_nearest_stop_m: int | None,
    time_delta_minutes: int | None,
    constraints: dict,
    recommendation: str,
) -> dict:
    return {
        "signal_type": signal_type,
        "route_id": route_id,
        "stop_candidates": stop_candidates,
        "distance_to_nearest_stop_m": distance_to_nearest_stop_m,
        "time_delta_minutes": time_delta_minutes,
        "constraints": constraints,
        "recommendation": recommendation,
    }
