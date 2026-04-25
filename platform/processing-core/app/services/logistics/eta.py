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
from app.services.logistics.repository import (
    get_last_tracking_event,
    get_latest_eta_snapshot,
    id_equals,
    refresh_by_id,
)
from app.services.logistics.service_client import LogisticsServiceClient
from neft_shared.settings import get_settings


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
    order = db.query(LogisticsOrder).filter(id_equals(LogisticsOrder.id, order_id)).one_or_none()
    if not order:
        return None

    service_error = None
    settings = get_settings()
    if settings.LOGISTICS_SERVICE_ENABLED and order.status != LogisticsOrderStatus.COMPLETED:
        try:
            snapshot = _compute_eta_snapshot_service(
                db,
                order=order,
                reason=reason,
                request_ctx=request_ctx,
            )
            if snapshot:
                return snapshot
        except RuntimeError:
            service_error = "LOGISTICS_UNAVAILABLE"

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
    if service_error:
        inputs["service_error"] = service_error
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
    db.flush()
    snapshot_id = str(snapshot.id)
    db.commit()
    snapshot = refresh_by_id(db, snapshot, LogisticsETASnapshot, snapshot_id)

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


def _compute_eta_snapshot_service(
    db: Session,
    *,
    order: LogisticsOrder,
    reason: str,
    request_ctx: RequestContext | None,
) -> LogisticsETASnapshot | None:
    route = repository.get_active_route(db, order_id=str(order.id))
    payload = _build_eta_payload(db, order=order, route_id=str(route.id) if route else None)
    if payload is None:
        return None
    client = LogisticsServiceClient()
    result = client.compute_eta(payload)
    now = _now()
    eta_end_at = now + timedelta(minutes=result.eta_minutes)
    method = (
        LogisticsETAMethod.SIMPLE_SPEED
        if order.status == LogisticsOrderStatus.IN_PROGRESS
        else LogisticsETAMethod.PLANNED
    )
    inputs = {
        "reason": reason,
        "status": order.status.value,
        "provider": result.provider,
        "service_eta_minutes": result.eta_minutes,
        "service_confidence": result.confidence,
        "service_explain": result.explain,
    }
    snapshot = LogisticsETASnapshot(
        order_id=str(order.id),
        computed_at=now,
        eta_end_at=eta_end_at,
        eta_confidence=int(round(result.confidence * 100)),
        method=method,
        inputs=inputs,
    )
    db.add(snapshot)
    db.flush()
    snapshot_id = str(snapshot.id)
    db.commit()
    snapshot = refresh_by_id(db, snapshot, LogisticsETASnapshot, snapshot_id)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_ETA_COMPUTED,
        entity_type="logistics_eta_snapshot",
        entity_id=str(snapshot.id),
        payload={
            "order_id": str(order.id),
            "eta_end_at": eta_end_at,
            "method": method.value,
            "confidence": snapshot.eta_confidence,
            "provider": result.provider,
        },
        request_ctx=request_ctx,
    )

    _capture_navigator_eta(db, order_id=str(order.id))
    return snapshot


def _build_eta_payload(
    db: Session,
    *,
    order: LogisticsOrder,
    route_id: str | None,
) -> dict | None:
    points = []
    events = repository.list_tracking_events(db, order_id=str(order.id), limit=10)
    for event in sorted(events, key=lambda item: item.ts):
        if event.lat is None or event.lon is None:
            continue
        points.append({"lat": event.lat, "lon": event.lon, "ts": event.ts.isoformat()})
    if len(points) < 2 and route_id:
        stops = repository.get_route_stops(db, route_id=route_id)
        for idx, stop in enumerate(stops):
            if stop.lat is None or stop.lon is None:
                continue
            points.append(
                {
                    "lat": stop.lat,
                    "lon": stop.lon,
                    "ts": (_now() + timedelta(minutes=idx)).isoformat(),
                }
            )
    if len(points) < 2:
        return None
    vehicle_type = (order.meta or {}).get("vehicle_type", "truck")
    fuel_type = (order.meta or {}).get("fuel_type", "diesel")
    return {
        "route_id": route_id or str(order.id),
        "points": points,
        "vehicle": {"type": vehicle_type, "fuel_type": fuel_type},
        "context": {},
    }


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
    # Rebuild ETA explain data from the latest local route snapshot.
    # The navigator contour here is evidence-only and separate from real routing transport ownership.
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
    if not navigator.can_replay_locally(snapshot.provider):
        # External preview providers keep truthful snapshot ownership, but ETA replay stays local-only.
        # Preserve the initial preview explain instead of pretending processing-core can re-run that provider.
        return
    adapter = navigator.get_local_evidence_adapter(snapshot.provider)
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
