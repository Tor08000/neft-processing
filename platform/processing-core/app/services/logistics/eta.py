from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.logistics import (
    LogisticsETAMethod,
    LogisticsETASnapshot,
    LogisticsOrder,
    LogisticsOrderStatus,
)
from app.services.audit_service import RequestContext
from app.services.logistics import events, navigator, repository
from app.services.logistics.repository import get_last_tracking_event, get_latest_eta_snapshot


_CONFIDENCE = {
    LogisticsETAMethod.PLANNED: 40,
    LogisticsETAMethod.SIMPLE_SPEED: 60,
    LogisticsETAMethod.LAST_KNOWN: 30,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _remaining_duration(order: LogisticsOrder, now: datetime) -> timedelta | None:
    planned_start_at = _ensure_aware(order.planned_start_at)
    planned_end_at = _ensure_aware(order.planned_end_at)
    actual_start_at = _ensure_aware(order.actual_start_at)

    if planned_start_at and planned_end_at:
        total = planned_end_at - planned_start_at
        started_at = actual_start_at or planned_start_at
        elapsed = now - started_at
        remaining = total - elapsed
        return remaining if remaining > timedelta(0) else timedelta(0)
    if planned_end_at:
        remaining = planned_end_at - now
        return remaining if remaining > timedelta(0) else timedelta(0)
    return None


def compute_eta_snapshot(
    db: Session,
    *,
    order_id: str,
    reason: str,
    request_ctx: RequestContext | None = None,
) -> LogisticsETASnapshot | None:
    order = db.query(LogisticsOrder).filter(LogisticsOrder.id == order_id).one_or_none()
    if not order:
        return None

    now = _now()
    last_event = get_last_tracking_event(db, order_id=order_id)
    planned_start_at = _ensure_aware(order.planned_start_at)
    planned_end_at = _ensure_aware(order.planned_end_at)
    actual_start_at = _ensure_aware(order.actual_start_at)
    actual_end_at = _ensure_aware(order.actual_end_at)
    remaining = _remaining_duration(order, now)

    if order.status == LogisticsOrderStatus.COMPLETED and actual_end_at:
        eta_end_at = actual_end_at
        method = LogisticsETAMethod.LAST_KNOWN
        confidence = 100
    elif order.status == LogisticsOrderStatus.PLANNED and planned_end_at:
        eta_end_at = planned_end_at
        method = LogisticsETAMethod.PLANNED
        confidence = _CONFIDENCE[method]
    elif order.status == LogisticsOrderStatus.IN_PROGRESS and remaining is not None:
        if last_event and last_event.speed_kmh is not None:
            method = LogisticsETAMethod.SIMPLE_SPEED
        elif last_event and last_event.lat is not None and last_event.lon is not None:
            method = LogisticsETAMethod.PLANNED
        else:
            method = LogisticsETAMethod.LAST_KNOWN
        eta_end_at = now + remaining
        confidence = _CONFIDENCE.get(method, 30)
    else:
        return None

    inputs = {
        "reason": reason,
        "status": order.status.value,
        "planned_start_at": planned_start_at,
        "planned_end_at": planned_end_at,
        "actual_start_at": actual_start_at,
        "actual_end_at": actual_end_at,
        "last_event_ts": last_event.ts if last_event else None,
        "last_speed_kmh": last_event.speed_kmh if last_event else None,
    }
    serialized_inputs = {key: _serialize_value(value) for key, value in inputs.items()}

    snapshot = LogisticsETASnapshot(
        order_id=order_id,
        computed_at=now,
        eta_end_at=eta_end_at,
        eta_confidence=int(confidence),
        method=method,
        inputs=serialized_inputs,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_ETA_COMPUTED,
        entity_type="logistics_eta_snapshot",
        entity_id=str(snapshot.id),
        payload={
            "order_id": order_id,
            "eta_end_at": eta_end_at,
            "method": method.value,
            "confidence": confidence,
        },
        request_ctx=request_ctx,
    )

    _capture_navigator_eta(db, order_id=order_id)

    return snapshot


def _serialize_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_or_compute_latest_eta(
    db: Session,
    *,
    order_id: str,
    request_ctx: RequestContext | None = None,
) -> LogisticsETASnapshot | None:
    latest = get_latest_eta_snapshot(db, order_id=order_id)
    last_event = get_last_tracking_event(db, order_id=order_id)
    if latest and last_event and latest.computed_at >= last_event.ts:
        if last_event.speed_kmh is not None and latest.method != LogisticsETAMethod.SIMPLE_SPEED:
            return compute_eta_snapshot(db, order_id=order_id, reason="on_demand", request_ctx=request_ctx)
        return latest
    if latest and last_event is None:
        return latest
    return compute_eta_snapshot(db, order_id=order_id, reason="on_demand", request_ctx=request_ctx)


def _capture_navigator_eta(db: Session, *, order_id: str) -> None:
    if not navigator.is_enabled():
        return
    route = repository.get_active_route(db, order_id=order_id)
    if not route:
        return
    snapshot = repository.get_latest_route_snapshot(db, route_id=str(route.id))
    if snapshot is None:
        stops = repository.get_route_stops(db, route_id=str(route.id))
        points = [
            navigator.GeoPoint(lat=stop.lat, lon=stop.lon)
            for stop in stops
            if stop.lat is not None and stop.lon is not None
        ]
        snapshot = navigator.create_route_snapshot(
            db,
            order_id=order_id,
            route_id=str(route.id),
            stops=points,
        )
    if snapshot is None or not snapshot.geometry:
        return
    adapter = navigator.get(snapshot.provider)
    geometry = [
        navigator.GeoPoint(lat=point["lat"], lon=point["lon"])
        for point in snapshot.geometry
        if isinstance(point, dict) and "lat" in point and "lon" in point
    ]
    if len(geometry) < 2:
        return
    route_snapshot = navigator.RouteSnapshot(
        provider=snapshot.provider,
        geometry=geometry,
        distance_km=snapshot.distance_km,
    )
    eta_result = adapter.estimate_eta(route_snapshot)
    navigator.create_eta_explain(db, route_snapshot=snapshot, eta_result=eta_result)
