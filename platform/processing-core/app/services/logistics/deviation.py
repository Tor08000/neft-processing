from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

from sqlalchemy.orm import Session

from app.models.logistics import (
    LogisticsDeviationEvent,
    LogisticsDeviationEventType,
    LogisticsDeviationSeverity,
    LogisticsOrder,
    LogisticsRiskSignal,
    LogisticsRiskSignalType,
    LogisticsRoute,
    LogisticsStop,
)
from app.services.audit_service import RequestContext
from app.services.logistics import events, repository
from app.services.logistics.defaults import (
    OFF_ROUTE_DEFAULTS,
    RISK_SIGNAL_DEFAULTS,
    ROUTE_CONSTRAINT_DEFAULTS,
    STOP_RADIUS_DEFAULTS,
    UNEXPECTED_STOP_DEFAULTS,
    VELOCITY_DEFAULTS,
)
from app.services.logistics.metrics import metrics as logistics_metrics
from app.services.logistics.utils import ensure_aware

@dataclass(frozen=True)
class DeviationResult:
    event: LogisticsDeviationEvent | None
    risk_signal: LogisticsRiskSignal | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2.0) ** 2
    return 2 * radius * asin(sqrt(a))


def _point_to_segment_distance_m(
    lat: float,
    lon: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    lat1, lon1 = start
    lat2, lon2 = end

    if lat1 == lat2 and lon1 == lon2:
        return _haversine_m(lat, lon, lat1, lon1)

    dx = lon2 - lon1
    dy = lat2 - lat1
    if dx == 0 and dy == 0:
        return _haversine_m(lat, lon, lat1, lon1)

    t = ((lon - lon1) * dx + (lat - lat1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_lon = lon1 + t * dx
    proj_lat = lat1 + t * dy
    return _haversine_m(lat, lon, proj_lat, proj_lon)


def _route_distance_m(point: tuple[float, float], stops: list[LogisticsStop]) -> float | None:
    lat, lon = point
    coords = [(stop.lat, stop.lon) for stop in stops if stop.lat is not None and stop.lon is not None]
    if len(coords) < 2:
        return None
    min_distance = None
    for start, end in zip(coords, coords[1:]):
        distance = _point_to_segment_distance_m(lat, lon, start, end)
        min_distance = distance if min_distance is None else min(min_distance, distance)
    return min_distance


def _load_state(order: LogisticsOrder) -> dict:
    meta = order.meta or {}
    return meta.get("deviation_state", {})


def _save_state(db: Session, *, order: LogisticsOrder, state: dict) -> None:
    meta = order.meta or {}
    meta["deviation_state"] = state
    order.meta = meta
    db.add(order)
    db.commit()


def _parse_state_ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_aware(value)
    try:
        return ensure_aware(datetime.fromisoformat(value))
    except (TypeError, ValueError):
        return None


def check_route_deviation(
    db: Session,
    *,
    order: LogisticsOrder,
    route: LogisticsRoute,
    lat: float,
    lon: float,
    ts: datetime | None = None,
    request_ctx: RequestContext | None = None,
) -> DeviationResult:
    constraint = repository.get_route_constraint(db, route_id=str(route.id))
    max_deviation = (
        constraint.max_route_deviation_m if constraint else ROUTE_CONSTRAINT_DEFAULTS.max_route_deviation_m
    )
    state = _load_state(order)
    event_ts = ensure_aware(ts or _now())
    last_ts = _parse_state_ts(state.get("last_ts"))
    if last_ts and event_ts <= last_ts:
        return DeviationResult(event=None, risk_signal=None)

    stops = repository.get_route_stops(db, route_id=str(route.id))
    distance = _route_distance_m((lat, lon), stops)
    if distance is None:
        return DeviationResult(event=None, risk_signal=None)

    status = state.get("status", "ON_ROUTE")
    consecutive_off = int(state.get("consecutive_off", 0))
    consecutive_on = int(state.get("consecutive_on", 0))
    pending_since = _parse_state_ts(state.get("pending_since"))
    confirmed_since = _parse_state_ts(state.get("confirmed_since"))
    last_signal_severity = state.get("last_signal_severity")

    if distance > max_deviation:
        consecutive_off += 1
        consecutive_on = 0
        if status in {"ON_ROUTE", "BACK_ON_ROUTE"}:
            status = "OFF_ROUTE_PENDING"
            pending_since = event_ts

        duration_minutes = int((event_ts - (pending_since or event_ts)).total_seconds() / 60)
        if status == "OFF_ROUTE_PENDING" and (
            consecutive_off >= OFF_ROUTE_DEFAULTS.off_route_consecutive_points
            or duration_minutes >= OFF_ROUTE_DEFAULTS.off_route_min_duration_minutes
        ):
            status = "OFF_ROUTE_CONFIRMED"
            confirmed_since = event_ts
            event = _create_deviation_event(
                db,
                order=order,
                route=route,
                event_type=LogisticsDeviationEventType.OFF_ROUTE,
                ts=event_ts,
                lat=lat,
                lon=lon,
                distance_from_route_m=int(distance),
                severity=LogisticsDeviationSeverity.MEDIUM,
                explain=_build_explain(
                    signal_type="OFF_ROUTE",
                    route_id=str(route.id),
                    distance_to_nearest_stop_m=int(distance),
                    time_delta_minutes=duration_minutes,
                    constraints=_constraint_payload(constraint),
                    recommendation="Check driver activity or routing accuracy",
                ),
                request_ctx=request_ctx,
            )
            risk_signal = _emit_risk_signal(
                db,
                order=order,
                signal_type=LogisticsRiskSignalType.ROUTE_DEVIATION_HIGH,
                severity=RISK_SIGNAL_DEFAULTS.off_route_severity,
                ts=event_ts,
                explain=_build_explain(
                    signal_type="ROUTE_DEVIATION_HIGH",
                    route_id=str(route.id),
                    distance_to_nearest_stop_m=int(distance),
                    time_delta_minutes=duration_minutes,
                    constraints=_constraint_payload(constraint),
                    recommendation="Check driver activity or routing accuracy",
                ),
                request_ctx=request_ctx,
            )
            logistics_metrics.inc("logistics_off_route_total")
            state.update({"last_signal_severity": RISK_SIGNAL_DEFAULTS.off_route_severity})
            state.update(
                {
                    "status": status,
                    "consecutive_off": consecutive_off,
                    "consecutive_on": consecutive_on,
                    "pending_since": pending_since.isoformat() if pending_since else None,
                    "confirmed_since": confirmed_since.isoformat() if confirmed_since else None,
                    "last_ts": event_ts.isoformat(),
                }
            )
            _save_state(db, order=order, state=state)
            return DeviationResult(event=event, risk_signal=risk_signal)

        if status == "OFF_ROUTE_CONFIRMED" and confirmed_since:
            duration_minutes = int((event_ts - confirmed_since).total_seconds() / 60)
            severity = _off_route_severity(duration_minutes)
            if severity and severity != last_signal_severity:
                risk_signal = _emit_risk_signal(
                    db,
                    order=order,
                    signal_type=LogisticsRiskSignalType.ROUTE_DEVIATION_HIGH,
                    severity=severity,
                    ts=event_ts,
                    explain=_build_explain(
                        signal_type="ROUTE_DEVIATION_HIGH",
                        route_id=str(route.id),
                        distance_to_nearest_stop_m=int(distance),
                        time_delta_minutes=duration_minutes,
                        constraints=_constraint_payload(constraint),
                        recommendation="Review route deviation duration and driver activity",
                    ),
                    request_ctx=request_ctx,
                )
                state["last_signal_severity"] = severity
                logistics_metrics.inc("logistics_off_route_total")
                state.update({"last_ts": event_ts.isoformat()})
                _save_state(db, order=order, state=state)
                return DeviationResult(event=None, risk_signal=risk_signal)

        state.update(
            {
                "status": status,
                "consecutive_off": consecutive_off,
                "consecutive_on": consecutive_on,
                "pending_since": pending_since.isoformat() if pending_since else None,
                "confirmed_since": confirmed_since.isoformat() if confirmed_since else None,
                "last_ts": event_ts.isoformat(),
            }
        )
        _save_state(db, order=order, state=state)
        return DeviationResult(event=None, risk_signal=None)

    consecutive_on += 1
    consecutive_off = 0
    if status in {"OFF_ROUTE_PENDING", "OFF_ROUTE_CONFIRMED"} and consecutive_on >= 2:
        status = "BACK_ON_ROUTE"
        event = _create_deviation_event(
            db,
            order=order,
            route=route,
            event_type=LogisticsDeviationEventType.BACK_ON_ROUTE,
            ts=event_ts,
            lat=lat,
            lon=lon,
            distance_from_route_m=int(distance),
            severity=LogisticsDeviationSeverity.LOW,
            explain=_build_explain(
                signal_type="BACK_ON_ROUTE",
                route_id=str(route.id),
                distance_to_nearest_stop_m=int(distance),
                time_delta_minutes=None,
                constraints=_constraint_payload(constraint),
                recommendation="Route deviation resolved",
            ),
            request_ctx=request_ctx,
        )
        state.update(
            {
                "status": status,
                "consecutive_off": consecutive_off,
                "consecutive_on": consecutive_on,
                "pending_since": None,
                "confirmed_since": None,
                "last_ts": event_ts.isoformat(),
            }
        )
        _save_state(db, order=order, state=state)
        return DeviationResult(event=event, risk_signal=None)

    if status == "BACK_ON_ROUTE" and consecutive_on >= 2:
        status = "ON_ROUTE"

    state.update(
        {
            "status": status,
            "consecutive_off": consecutive_off,
            "consecutive_on": consecutive_on,
            "pending_since": None,
            "confirmed_since": None,
            "last_ts": event_ts.isoformat(),
        }
    )
    _save_state(db, order=order, state=state)

    return DeviationResult(event=None, risk_signal=None)


def check_stop_radius(
    db: Session,
    *,
    order: LogisticsOrder,
    route: LogisticsRoute,
    stop: LogisticsStop,
    lat: float,
    lon: float,
    ts: datetime | None = None,
    request_ctx: RequestContext | None = None,
) -> DeviationResult:
    constraint = repository.get_route_constraint(db, route_id=str(route.id))

    if stop.lat is None or stop.lon is None:
        return DeviationResult(event=None, risk_signal=None)

    distance = _haversine_m(lat, lon, stop.lat, stop.lon)
    max_stop_radius = constraint.max_stop_radius_m if constraint else STOP_RADIUS_DEFAULTS.stop_out_of_radius_m
    if distance <= max_stop_radius:
        return DeviationResult(event=None, risk_signal=None)

    event_ts = ts or _now()
    severity = LogisticsDeviationSeverity.MEDIUM
    signal_severity = RISK_SIGNAL_DEFAULTS.fuel_stop_mismatch_severity
    if distance > STOP_RADIUS_DEFAULTS.stop_out_of_radius_high_m:
        severity = LogisticsDeviationSeverity.HIGH
        signal_severity = RISK_SIGNAL_DEFAULTS.stop_out_of_radius_high_severity
    event = _create_deviation_event(
        db,
        order=order,
        route=route,
        event_type=LogisticsDeviationEventType.STOP_OUT_OF_RADIUS,
        ts=event_ts,
        lat=lat,
        lon=lon,
        distance_from_route_m=int(distance),
        stop_id=str(stop.id),
        severity=severity,
        explain=_build_explain(
            signal_type="STOP_OUT_OF_RADIUS",
            route_id=str(route.id),
            distance_to_nearest_stop_m=int(distance),
            time_delta_minutes=None,
            constraints=_constraint_payload(constraint),
            recommendation="Verify stop coordinates and driver compliance",
        ),
        request_ctx=request_ctx,
    )
    risk_signal = _emit_risk_signal(
        db,
        order=order,
        signal_type=LogisticsRiskSignalType.ROUTE_DEVIATION_HIGH,
        severity=signal_severity,
        ts=event_ts,
        explain=_build_explain(
            signal_type="ROUTE_DEVIATION_HIGH",
            route_id=str(route.id),
            distance_to_nearest_stop_m=int(distance),
            time_delta_minutes=None,
            constraints=_constraint_payload(constraint),
            recommendation="Verify stop adherence",
        ),
        request_ctx=request_ctx,
    )
    return DeviationResult(event=event, risk_signal=risk_signal)


def check_unexpected_stop(
    db: Session,
    *,
    order: LogisticsOrder,
    route: LogisticsRoute,
    ts: datetime,
    speed_kmh: float | None,
    stop_id: str | None,
    previous_event,
    request_ctx: RequestContext | None = None,
) -> DeviationResult:
    if speed_kmh is None or speed_kmh > UNEXPECTED_STOP_DEFAULTS.stop_speed_threshold_kmh or stop_id:
        return DeviationResult(event=None, risk_signal=None)

    last_event = previous_event
    if (
        not last_event
        or last_event.speed_kmh is None
        or last_event.speed_kmh > UNEXPECTED_STOP_DEFAULTS.stop_speed_threshold_kmh
    ):
        return DeviationResult(event=None, risk_signal=None)

    delta_minutes = int((ts - last_event.ts).total_seconds() / 60)
    if delta_minutes < UNEXPECTED_STOP_DEFAULTS.unexpected_stop_min_duration_minutes:
        return DeviationResult(event=None, risk_signal=None)

    event = _create_deviation_event(
        db,
        order=order,
        route=route,
        event_type=LogisticsDeviationEventType.UNEXPECTED_STOP,
        ts=ts,
        lat=last_event.lat,
        lon=last_event.lon,
        distance_from_route_m=None,
        severity=LogisticsDeviationSeverity.LOW,
        explain=_build_explain(
            signal_type="UNEXPECTED_STOP",
            route_id=str(route.id),
            distance_to_nearest_stop_m=None,
            time_delta_minutes=delta_minutes,
            constraints=_constraint_payload(repository.get_route_constraint(db, route_id=str(route.id))),
            recommendation="Check stop justification",
        ),
        request_ctx=request_ctx,
    )
    risk_signal = None
    if delta_minutes >= 90:
        risk_signal = _emit_risk_signal(
            db,
            order=order,
            signal_type=LogisticsRiskSignalType.ROUTE_DEVIATION_HIGH,
            severity=RISK_SIGNAL_DEFAULTS.unexpected_stop_90m_severity,
            ts=ts,
            explain=_build_explain(
                signal_type="UNEXPECTED_STOP",
                route_id=str(route.id),
                distance_to_nearest_stop_m=None,
                time_delta_minutes=delta_minutes,
                constraints=_constraint_payload(repository.get_route_constraint(db, route_id=str(route.id))),
                recommendation="Investigate prolonged stop",
            ),
            request_ctx=request_ctx,
        )
    elif delta_minutes >= 40:
        risk_signal = _emit_risk_signal(
            db,
            order=order,
            signal_type=LogisticsRiskSignalType.ROUTE_DEVIATION_HIGH,
            severity=RISK_SIGNAL_DEFAULTS.unexpected_stop_40m_severity,
            ts=ts,
            explain=_build_explain(
                signal_type="UNEXPECTED_STOP",
                route_id=str(route.id),
                distance_to_nearest_stop_m=None,
                time_delta_minutes=delta_minutes,
                constraints=_constraint_payload(repository.get_route_constraint(db, route_id=str(route.id))),
                recommendation="Investigate prolonged stop",
            ),
            request_ctx=request_ctx,
        )
    return DeviationResult(event=event, risk_signal=risk_signal)


def check_velocity_anomaly(
    db: Session,
    *,
    order: LogisticsOrder,
    route: LogisticsRoute,
    previous_event,
    current_ts: datetime,
    lat: float,
    lon: float,
    request_ctx: RequestContext | None,
) -> LogisticsRiskSignal | None:
    if not previous_event or previous_event.lat is None or previous_event.lon is None:
        return None
    current_ts = ensure_aware(current_ts)
    previous_ts = ensure_aware(previous_event.ts)
    time_delta = (current_ts - previous_ts).total_seconds() / 3600
    if time_delta <= 0:
        return None
    distance = _haversine_m(lat, lon, previous_event.lat, previous_event.lon) / 1000
    implied_speed = distance / time_delta
    if distance * 1000 < VELOCITY_DEFAULTS.teleport_min_distance_m:
        return None
    if implied_speed < VELOCITY_DEFAULTS.teleport_speed_kmh:
        return None
    return _emit_risk_signal(
        db,
        order=order,
        signal_type=LogisticsRiskSignalType.VELOCITY_ANOMALY,
        severity=RISK_SIGNAL_DEFAULTS.velocity_anomaly_severity,
        ts=current_ts,
        explain=_build_explain(
            signal_type="VELOCITY_ANOMALY",
            route_id=str(route.id),
            distance_to_nearest_stop_m=int(distance * 1000),
            time_delta_minutes=int(time_delta * 60),
            constraints=_constraint_payload(repository.get_route_constraint(db, route_id=str(route.id))),
            recommendation="Review tracking device consistency",
        ),
        request_ctx=request_ctx,
    )


def _meets_off_route_threshold(
    events: list,
    stops: list[LogisticsStop],
    max_deviation: int,
    current_ts: datetime,
    min_duration_minutes: int,
) -> bool:
    if len(events) < OFF_ROUTE_DEFAULTS.off_route_consecutive_points:
        return False
    off_route_events = []
    for event in events:
        if event.lat is None or event.lon is None:
            break
        distance = _route_distance_m((event.lat, event.lon), stops)
        if distance is None or distance <= max_deviation:
            break
        off_route_events.append(event)
    if len(off_route_events) < OFF_ROUTE_DEFAULTS.off_route_consecutive_points:
        return False
    oldest = off_route_events[-1]
    duration = int((ensure_aware(current_ts) - ensure_aware(oldest.ts)).total_seconds() / 60)
    return duration >= min_duration_minutes


def _off_route_severity(duration_minutes: int) -> int | None:
    if duration_minutes >= 60:
        return RISK_SIGNAL_DEFAULTS.off_route_severity_60m
    if duration_minutes >= 30:
        return RISK_SIGNAL_DEFAULTS.off_route_severity_30m
    return None


def _has_recent_signal(db: Session, *, order_id: str, severity: int) -> bool:
    signals = repository.list_risk_signals(db, order_id=order_id, limit=1)
    if not signals:
        return False
    last_signal = signals[0]
    return last_signal.signal_type == LogisticsRiskSignalType.ROUTE_DEVIATION_HIGH and last_signal.severity >= severity


def _constraint_payload(constraint) -> dict:
    return {
        "max_stop_radius_m": constraint.max_stop_radius_m if constraint else STOP_RADIUS_DEFAULTS.stop_out_of_radius_m,
        "allowed_fuel_window_minutes": constraint.allowed_fuel_window_minutes
        if constraint
        else ROUTE_CONSTRAINT_DEFAULTS.allowed_fuel_window_minutes,
    }


def _build_explain(
    *,
    signal_type: str,
    route_id: str | None,
    distance_to_nearest_stop_m: int | None,
    time_delta_minutes: int | None,
    constraints: dict,
    recommendation: str,
) -> dict:
    return {
        "signal_type": signal_type,
        "route_id": route_id,
        "distance_to_nearest_stop_m": distance_to_nearest_stop_m,
        "time_delta_minutes": time_delta_minutes,
        "constraints": constraints,
        "recommendation": recommendation,
    }


def _create_deviation_event(
    db: Session,
    *,
    order: LogisticsOrder,
    route: LogisticsRoute,
    event_type: LogisticsDeviationEventType,
    ts: datetime,
    lat: float | None,
    lon: float | None,
    distance_from_route_m: int | None,
    severity: LogisticsDeviationSeverity,
    explain: dict,
    stop_id: str | None = None,
    request_ctx: RequestContext | None = None,
) -> LogisticsDeviationEvent:
    event = LogisticsDeviationEvent(
        order_id=str(order.id),
        route_id=str(route.id),
        event_type=event_type,
        ts=ts,
        lat=lat,
        lon=lon,
        distance_from_route_m=distance_from_route_m,
        stop_id=stop_id,
        severity=severity,
        explain=explain,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    events.audit_event(
        db,
        event_type=_audit_event_for(event_type),
        entity_type="logistics_deviation_event",
        entity_id=str(event.id),
        payload={
            "order_id": str(order.id),
            "route_id": str(route.id),
            "event_type": event.event_type.value,
            "severity": event.severity.value,
        },
        request_ctx=request_ctx,
    )
    events.register_deviation_event_node(
        db,
        tenant_id=order.tenant_id,
        order_id=str(order.id),
        deviation_id=str(event.id),
        request_ctx=request_ctx,
    )
    return event


def _emit_risk_signal(
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
    db.commit()
    db.refresh(signal)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_RISK_SIGNAL_EMITTED,
        entity_type="logistics_risk_signal",
        entity_id=str(signal.id),
        payload={
            "order_id": str(order.id),
            "signal_type": signal.signal_type.value,
            "severity": signal.severity,
        },
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


def _audit_event_for(event_type: LogisticsDeviationEventType) -> str:
    if event_type == LogisticsDeviationEventType.OFF_ROUTE:
        return events.LOGISTICS_OFF_ROUTE_DETECTED
    if event_type == LogisticsDeviationEventType.BACK_ON_ROUTE:
        return events.LOGISTICS_BACK_ON_ROUTE
    if event_type == LogisticsDeviationEventType.STOP_OUT_OF_RADIUS:
        return events.LOGISTICS_STOP_OUT_OF_RADIUS
    return events.LOGISTICS_UNEXPECTED_STOP
