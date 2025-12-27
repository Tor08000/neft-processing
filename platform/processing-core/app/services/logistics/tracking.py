from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.logistics import (
    LogisticsOrder,
    LogisticsOrderStatus,
    LogisticsStopStatus,
    LogisticsTrackingEvent,
    LogisticsTrackingEventType,
)
from app.schemas.logistics import LogisticsTrackingEventIn
from app.services.audit_service import RequestContext
from app.services.logistics import eta, events
from app.services.logistics.repository import count_tracking_events, get_stop


class LogisticsTrackingError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ingest_tracking_event(
    db: Session,
    *,
    order_id: str,
    payload: LogisticsTrackingEventIn,
    request_ctx: RequestContext | None = None,
) -> LogisticsTrackingEvent:
    order = db.query(LogisticsOrder).filter(LogisticsOrder.id == order_id).one_or_none()
    if not order:
        raise LogisticsTrackingError("order_not_found")

    event_ts = payload.ts or _now()
    event = LogisticsTrackingEvent(
        order_id=order_id,
        vehicle_id=payload.vehicle_id or order.vehicle_id,
        driver_id=payload.driver_id or order.driver_id,
        event_type=payload.event_type,
        ts=event_ts,
        lat=payload.lat,
        lon=payload.lon,
        speed_kmh=payload.speed_kmh,
        heading_deg=payload.heading_deg,
        odometer_km=payload.odometer_km,
        stop_id=payload.stop_id,
        status_from=payload.status_from,
        status_to=payload.status_to,
        meta=payload.meta,
    )
    db.add(event)

    if payload.event_type == LogisticsTrackingEventType.STATUS_CHANGE and payload.status_to:
        try:
            next_status = LogisticsOrderStatus(payload.status_to)
        except ValueError as exc:
            raise LogisticsTrackingError("invalid_status") from exc
        order.status = next_status
    stop_event_type: str | None = None
    if payload.event_type in {LogisticsTrackingEventType.STOP_ARRIVAL, LogisticsTrackingEventType.STOP_DEPARTURE}:
        if not payload.stop_id:
            raise LogisticsTrackingError("stop_required")
        stop = get_stop(db, stop_id=payload.stop_id)
        if not stop:
            raise LogisticsTrackingError("stop_not_found")
        if payload.event_type == LogisticsTrackingEventType.STOP_ARRIVAL:
            stop.actual_arrival_at = event_ts
            stop.status = LogisticsStopStatus.ARRIVED
            stop_event_type = events.LOGISTICS_STOP_ARRIVED
        else:
            stop.actual_departure_at = event_ts
            stop.status = LogisticsStopStatus.DEPARTED
            stop_event_type = events.LOGISTICS_STOP_DEPARTED
    if payload.event_type == LogisticsTrackingEventType.FUEL_STOP_LINKED and payload.stop_id:
        stop = get_stop(db, stop_id=payload.stop_id)
        if stop and payload.meta and payload.meta.get("fuel_tx_id"):
            stop.fuel_tx_id = payload.meta.get("fuel_tx_id")

    db.commit()
    db.refresh(event)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_TRACKING_EVENT_INGESTED,
        entity_type="logistics_tracking_event",
        entity_id=str(event.id),
        payload={
            "order_id": order_id,
            "event_type": event.event_type.value,
            "ts": event.ts,
        },
        request_ctx=request_ctx,
    )
    if stop_event_type:
        events.audit_event(
            db,
            event_type=stop_event_type,
            entity_type="logistics_stop",
            entity_id=payload.stop_id,
            payload={"order_id": order_id, "stop_id": payload.stop_id, "ts": event_ts},
            request_ctx=request_ctx,
        )

    total_events = count_tracking_events(db, order_id=order_id)
    if payload.event_type in {LogisticsTrackingEventType.STOP_ARRIVAL, LogisticsTrackingEventType.STOP_DEPARTURE}:
        eta.compute_eta_snapshot(db, order_id=order_id, reason="stop_event", request_ctx=request_ctx)
    elif total_events % 10 == 0:
        eta.compute_eta_snapshot(db, order_id=order_id, reason="tracking_batch", request_ctx=request_ctx)

    return event
