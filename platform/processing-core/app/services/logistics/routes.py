from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.logistics import (
    LogisticsOrder,
    LogisticsRoute,
    LogisticsRouteStatus,
    LogisticsStop,
    LogisticsStopStatus,
)
from app.schemas.logistics import LogisticsStopIn
from app.services.audit_service import RequestContext
from app.services.logistics import events, navigator
from app.services.logistics.repository import get_route, get_route_stops


class LogisticsRouteError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_route(
    db: Session,
    *,
    order_id: str,
    distance_km: float | None = None,
    planned_duration_minutes: int | None = None,
    request_ctx: RequestContext | None = None,
) -> LogisticsRoute:
    order = db.query(LogisticsOrder).filter(LogisticsOrder.id == order_id).one_or_none()
    if not order:
        raise LogisticsRouteError("order_not_found")

    latest_version = (
        db.query(LogisticsRoute)
        .filter(LogisticsRoute.order_id == order_id)
        .order_by(LogisticsRoute.version.desc())
        .first()
    )
    next_version = (latest_version.version + 1) if latest_version else 1

    route = LogisticsRoute(
        order_id=order_id,
        version=next_version,
        status=LogisticsRouteStatus.DRAFT,
        distance_km=distance_km,
        planned_duration_minutes=planned_duration_minutes,
        created_at=_now(),
    )
    db.add(route)
    db.commit()
    db.refresh(route)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_ROUTE_CREATED,
        entity_type="logistics_route",
        entity_id=str(route.id),
        payload={
            "order_id": order_id,
            "version": route.version,
            "status": route.status.value,
        },
        request_ctx=request_ctx,
    )
    events.register_route_node(
        db,
        tenant_id=order.tenant_id,
        order_id=order_id,
        route_id=str(route.id),
        request_ctx=request_ctx,
    )
    stops = get_route_stops(db, route_id=str(route.id))
    _snapshot_from_stops(db, order_id=order_id, route_id=str(route.id), stops=stops)
    return route


def activate_route(
    db: Session,
    *,
    route_id: str,
    request_ctx: RequestContext | None = None,
) -> LogisticsRoute:
    route = get_route(db, route_id=route_id)
    if not route:
        raise LogisticsRouteError("route_not_found")

    if route.status != LogisticsRouteStatus.ACTIVE:
        db.query(LogisticsRoute).filter(LogisticsRoute.order_id == route.order_id).filter(
            LogisticsRoute.status == LogisticsRouteStatus.ACTIVE
        ).update({"status": LogisticsRouteStatus.ARCHIVED})
        route.status = LogisticsRouteStatus.ACTIVE
        db.commit()
        db.refresh(route)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_ROUTE_ACTIVATED,
        entity_type="logistics_route",
        entity_id=str(route.id),
        payload={"status": route.status.value},
        request_ctx=request_ctx,
    )
    return route


def upsert_stops(
    db: Session,
    *,
    route_id: str,
    stops: list[LogisticsStopIn],
    request_ctx: RequestContext | None = None,
) -> list[LogisticsStop]:
    route = get_route(db, route_id=route_id)
    if not route:
        raise LogisticsRouteError("route_not_found")

    sequences = [stop.sequence for stop in stops]
    duplicates = [seq for seq, count in Counter(sequences).items() if count > 1]
    if duplicates:
        raise LogisticsRouteError("duplicate_sequences")

    existing_stops = {str(stop.id): stop for stop in get_route_stops(db, route_id=route_id)}
    updated: list[LogisticsStop] = []

    for payload in stops:
        stop = existing_stops.get(payload.id) if payload.id else None
        if stop is None:
            stop = LogisticsStop(
                route_id=route_id,
                sequence=payload.sequence,
                stop_type=payload.stop_type,
                name=payload.name,
                address_text=payload.address_text,
                lat=payload.lat,
                lon=payload.lon,
                planned_arrival_at=payload.planned_arrival_at,
                planned_departure_at=payload.planned_departure_at,
                actual_arrival_at=payload.actual_arrival_at,
                actual_departure_at=payload.actual_departure_at,
                status=payload.status or LogisticsStopStatus.PENDING,
                fuel_tx_id=payload.fuel_tx_id,
                meta=payload.meta,
            )
            db.add(stop)
        else:
            stop.sequence = payload.sequence
            stop.stop_type = payload.stop_type
            stop.name = payload.name
            stop.address_text = payload.address_text
            stop.lat = payload.lat
            stop.lon = payload.lon
            stop.planned_arrival_at = payload.planned_arrival_at
            stop.planned_departure_at = payload.planned_departure_at
            stop.actual_arrival_at = payload.actual_arrival_at
            stop.actual_departure_at = payload.actual_departure_at
            stop.status = payload.status or stop.status
            stop.fuel_tx_id = payload.fuel_tx_id
            stop.meta = payload.meta
        updated.append(stop)

    db.commit()
    for stop in updated:
        db.refresh(stop)

    order = db.query(LogisticsOrder).filter(LogisticsOrder.id == route.order_id).one_or_none()
    tenant_id = order.tenant_id if order else None
    if tenant_id is not None:
        for stop in updated:
            events.register_stop_node(
                db,
                tenant_id=tenant_id,
                route_id=route_id,
                stop_id=str(stop.id),
                request_ctx=request_ctx,
            )
            events.link_stop_relations(
                db,
                tenant_id=tenant_id,
                stop_id=str(stop.id),
                vehicle_id=str(order.vehicle_id) if order and order.vehicle_id else None,
                driver_id=str(order.driver_id) if order and order.driver_id else None,
                fuel_tx_id=str(stop.fuel_tx_id) if stop.fuel_tx_id else None,
                request_ctx=request_ctx,
            )

    _snapshot_from_stops(db, order_id=str(route.order_id), route_id=str(route.id), stops=updated)

    return updated


def _snapshot_from_stops(
    db: Session, *, order_id: str, route_id: str, stops: list[LogisticsStop]
) -> None:
    points = [
        navigator.GeoPoint(lat=stop.lat, lon=stop.lon)
        for stop in stops
        if stop.lat is not None and stop.lon is not None
    ]
    navigator.create_route_snapshot(db, order_id=order_id, route_id=route_id, stops=points)
