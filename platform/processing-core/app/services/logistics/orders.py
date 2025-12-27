from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.fleet import FleetDriver, FleetVehicle
from app.models.logistics import LogisticsOrder, LogisticsOrderStatus, LogisticsOrderType
from app.services.audit_service import RequestContext
from app.services.logistics import eta, events
from app.services.logistics.repository import get_order


class LogisticsOrderError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_vehicle_driver(db: Session, *, vehicle_id: str | None, driver_id: str | None) -> None:
    if vehicle_id:
        exists = db.query(FleetVehicle).filter(FleetVehicle.id == vehicle_id).one_or_none()
        if not exists:
            raise LogisticsOrderError("vehicle_not_found")
    if driver_id:
        exists = db.query(FleetDriver).filter(FleetDriver.id == driver_id).one_or_none()
        if not exists:
            raise LogisticsOrderError("driver_not_found")


def create_order(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    order_type: LogisticsOrderType,
    status: LogisticsOrderStatus | None = None,
    vehicle_id: str | None = None,
    driver_id: str | None = None,
    planned_start_at: datetime | None = None,
    planned_end_at: datetime | None = None,
    origin_text: str | None = None,
    destination_text: str | None = None,
    meta: dict | None = None,
    request_ctx: RequestContext | None = None,
) -> LogisticsOrder:
    _ensure_vehicle_driver(db, vehicle_id=vehicle_id, driver_id=driver_id)
    order_status = status or LogisticsOrderStatus.DRAFT
    order = LogisticsOrder(
        tenant_id=tenant_id,
        client_id=client_id,
        order_type=order_type,
        status=order_status,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        planned_start_at=planned_start_at,
        planned_end_at=planned_end_at,
        origin_text=origin_text,
        destination_text=destination_text,
        meta=meta,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_ORDER_CREATED,
        entity_type="logistics_order",
        entity_id=str(order.id),
        payload={
            "tenant_id": order.tenant_id,
            "client_id": order.client_id,
            "order_type": order.order_type.value,
            "status": order.status.value,
        },
        request_ctx=request_ctx,
    )
    events.register_order_node(db, tenant_id=order.tenant_id, order_id=str(order.id), request_ctx=request_ctx)
    return order


def start_order(
    db: Session,
    *,
    order_id: str,
    started_at: datetime | None = None,
    request_ctx: RequestContext | None = None,
) -> LogisticsOrder:
    order = get_order(db, order_id=order_id)
    if not order:
        raise LogisticsOrderError("order_not_found")
    if order.status not in {LogisticsOrderStatus.DRAFT, LogisticsOrderStatus.PLANNED}:
        raise LogisticsOrderError("invalid_status")

    order.status = LogisticsOrderStatus.IN_PROGRESS
    order.actual_start_at = started_at or _now()
    db.commit()
    db.refresh(order)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_ORDER_STARTED,
        entity_type="logistics_order",
        entity_id=str(order.id),
        payload={"status": order.status.value, "actual_start_at": order.actual_start_at},
        request_ctx=request_ctx,
    )
    eta.compute_eta_snapshot(db, order_id=str(order.id), reason="order_started", request_ctx=request_ctx)
    return order


def complete_order(
    db: Session,
    *,
    order_id: str,
    completed_at: datetime | None = None,
    request_ctx: RequestContext | None = None,
) -> LogisticsOrder:
    order = get_order(db, order_id=order_id)
    if not order:
        raise LogisticsOrderError("order_not_found")
    if order.status not in {LogisticsOrderStatus.IN_PROGRESS, LogisticsOrderStatus.PLANNED}:
        raise LogisticsOrderError("invalid_status")

    order.status = LogisticsOrderStatus.COMPLETED
    order.actual_end_at = completed_at or _now()
    db.commit()
    db.refresh(order)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_ORDER_COMPLETED,
        entity_type="logistics_order",
        entity_id=str(order.id),
        payload={"status": order.status.value, "actual_end_at": order.actual_end_at},
        request_ctx=request_ctx,
    )
    eta.compute_eta_snapshot(db, order_id=str(order.id), reason="order_completed", request_ctx=request_ctx)
    return order


def cancel_order(
    db: Session,
    *,
    order_id: str,
    request_ctx: RequestContext | None = None,
) -> LogisticsOrder:
    order = get_order(db, order_id=order_id)
    if not order:
        raise LogisticsOrderError("order_not_found")
    if order.status in {LogisticsOrderStatus.COMPLETED, LogisticsOrderStatus.CANCELLED}:
        raise LogisticsOrderError("invalid_status")

    order.status = LogisticsOrderStatus.CANCELLED
    db.commit()
    db.refresh(order)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_ORDER_CANCELLED,
        entity_type="logistics_order",
        entity_id=str(order.id),
        payload={"status": order.status.value},
        request_ctx=request_ctx,
    )
    return order

