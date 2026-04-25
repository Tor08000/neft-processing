from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fleet import FleetDriver, FleetVehicle
from app.models.fuel import FuelTransaction
from app.models.logistics import (
    LogisticsDeviationEvent,
    LogisticsDeviationEventType,
    LogisticsDeviationSeverity,
    LogisticsETASnapshot,
    LogisticsFuelAlertSeverity,
    LogisticsFuelAlertStatus,
    LogisticsFuelAlertType,
    LogisticsOrder,
    LogisticsOrderStatus,
    LogisticsOrderType,
    LogisticsStopStatus,
    LogisticsStopType,
    LogisticsTrackingEvent,
)
from app.schemas.logistics import LogisticsStopIn
from app.security.client_auth import require_client_user
from app.services.audit_service import AuditService, AuditVisibility, request_context_from_request
from app.services.logistics import fuel_linker_service, orders as logistics_orders, repository, routes as logistics_routes
from app.services.logistics.orders import LogisticsOrderError
from app.services.logistics.routes import LogisticsRouteError
from app.services.logistics.service_client import LogisticsServiceClient
from app.services.token_claims import DEFAULT_TENANT_ID, resolve_token_tenant_id

router = APIRouter(prefix="/client/logistics", tags=["client-logistics"])

_LOGISTICS_READ_TABLES = (
    "fleet_vehicles",
    "fleet_drivers",
    "logistics_orders",
    "logistics_routes",
    "logistics_stops",
    "logistics_tracking_events",
    "logistics_eta_snapshots",
    "logistics_deviation_events",
)

_LOGISTICS_FUEL_TABLES = (
    "fuel_transactions",
    "fuel_stations",
    "fuel_networks",
    "fuel_cards",
    "logistics_fuel_links",
    "logistics_fuel_alerts",
)

_LOGISTICS_WRITE_TABLES = _LOGISTICS_READ_TABLES + (
    "logistics_route_snapshots",
    "logistics_navigator_explains",
    "audit_log",
    "legal_nodes",
    "legal_edges",
)


class ClientTripPointIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, max_length=256)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    planned_at: datetime | None = None


class ClientTripCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=128)
    vehicle_id: str | None = None
    driver_id: str | None = None
    start_planned_at: datetime | None = None
    end_planned_at: datetime | None = None
    origin: ClientTripPointIn
    destination: ClientTripPointIn
    stops: list[ClientTripPointIn] = Field(default_factory=list, max_length=20)
    distance_km: float | None = Field(default=None, ge=0)
    planned_duration_minutes: int | None = Field(default=None, ge=0)
    meta: dict[str, Any] | None = None


class ClientFuelConsumptionWriteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_id: str
    distance_km: float = Field(ge=0)
    vehicle_kind: str = Field(default="truck", max_length=64)
    idempotency_key: str | None = Field(default=None, max_length=128)


def _table_exists(db: Session, name: str) -> bool:
    bind = db.get_bind()
    if bind is None:
        return False
    return sa_inspect(bind).has_table(name)


def _require_tables(db: Session, tables: tuple[str, ...]) -> None:
    missing = [name for name in tables if not _table_exists(db, name)]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "logistics_not_configured", "missing_tables": missing},
        )


def _client_id_from_token(token: dict[str, Any]) -> str:
    client_id = str(token.get("client_id") or "").strip()
    if not client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="client_not_linked")
    return client_id


def _parse_datetime(raw: str | None, *, field_name: str) -> datetime | None:
    if raw is None or raw == "":
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid_datetime:{field_name}") from exc


def _parse_guid(
    raw: str,
    *,
    field_name: str,
    error_status: int = status.HTTP_400_BAD_REQUEST,
    error_detail: str | None = None,
) -> str:
    try:
        return str(uuid.UUID(str(raw).strip()))
    except (AttributeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=error_status,
            detail=error_detail or f"invalid_uuid:{field_name}",
        ) from exc


def _trip_status_for_portal(order_status: LogisticsOrderStatus) -> str:
    if order_status in {LogisticsOrderStatus.DRAFT, LogisticsOrderStatus.PLANNED}:
        return "CREATED"
    return order_status.value


def _trip_filter_statuses(status_code: str | None) -> tuple[LogisticsOrderStatus, ...] | None:
    if not status_code:
        return None
    normalized = status_code.strip().upper()
    if normalized == "CREATED":
        return (LogisticsOrderStatus.DRAFT, LogisticsOrderStatus.PLANNED)
    if normalized == "IN_PROGRESS":
        return (LogisticsOrderStatus.IN_PROGRESS,)
    if normalized == "COMPLETED":
        return (LogisticsOrderStatus.COMPLETED,)
    if normalized == "CANCELLED":
        return (LogisticsOrderStatus.CANCELLED,)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_trip_status")


def _route_stop_type(stop_type: str) -> str:
    if stop_type == "START":
        return "START"
    if stop_type == "END":
        return "END"
    return "STOP"


def _severity_for_portal(severity: LogisticsDeviationSeverity) -> str:
    if severity == LogisticsDeviationSeverity.HIGH:
        return "CRITICAL"
    if severity == LogisticsDeviationSeverity.MEDIUM:
        return "WARN"
    return "INFO"


def _impact_level_for_severity(severity: LogisticsDeviationSeverity | None) -> str:
    if severity == LogisticsDeviationSeverity.HIGH:
        return "HIGH"
    if severity == LogisticsDeviationSeverity.MEDIUM:
        return "MEDIUM"
    if severity == LogisticsDeviationSeverity.LOW:
        return "LOW"
    return "NONE"


def _severity_rank(severity: LogisticsDeviationSeverity) -> int:
    if severity == LogisticsDeviationSeverity.HIGH:
        return 3
    if severity == LogisticsDeviationSeverity.MEDIUM:
        return 2
    return 1


def _deviation_type_for_portal(event_type: LogisticsDeviationEventType) -> str:
    if event_type == LogisticsDeviationEventType.UNEXPECTED_STOP:
        return "UNEXPECTED_STOP"
    return "ROUTE_DEVIATION"


def _deviation_type_filter(type_code: str | None) -> tuple[LogisticsDeviationEventType, ...] | None:
    if not type_code:
        return None
    normalized = type_code.strip().upper()
    if normalized == "ALL":
        return None
    if normalized == "LATE_START":
        return ()
    if normalized == "ROUTE_DEVIATION":
        return (
            LogisticsDeviationEventType.OFF_ROUTE,
            LogisticsDeviationEventType.BACK_ON_ROUTE,
            LogisticsDeviationEventType.STOP_OUT_OF_RADIUS,
        )
    if normalized == "UNEXPECTED_STOP":
        return (LogisticsDeviationEventType.UNEXPECTED_STOP,)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_deviation_type")


def _fuel_alert_type(type_code: str | None) -> LogisticsFuelAlertType | None:
    if not type_code:
        return None
    try:
        return LogisticsFuelAlertType(type_code.strip().upper())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_fuel_alert_type") from exc


def _fuel_alert_severity(severity_code: str | None) -> LogisticsFuelAlertSeverity | None:
    if not severity_code:
        return None
    try:
        return LogisticsFuelAlertSeverity(severity_code.strip().upper())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_fuel_alert_severity") from exc


def _fuel_alert_status(status_code: str | None) -> LogisticsFuelAlertStatus | None:
    if not status_code:
        return None
    try:
        return LogisticsFuelAlertStatus(status_code.strip().upper())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_fuel_alert_status") from exc


def _format_point(label: str | None, *, lat: float | None = None, lon: float | None = None) -> dict[str, Any] | None:
    if label is None and lat is None and lon is None:
        return None
    return {"label": label, "lat": lat, "lon": lon}


def _point_label(point: ClientTripPointIn) -> str | None:
    if point.label:
        return point.label.strip() or None
    return None


def _validate_trip_point(point: ClientTripPointIn, *, field_name: str, require_location: bool) -> None:
    has_label = bool(_point_label(point))
    has_lat = point.lat is not None
    has_lon = point.lon is not None
    if has_lat != has_lon:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_trip_point:{field_name}:coordinates_pair_required",
        )
    if require_location and not has_label and not (has_lat and has_lon):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_trip_point:{field_name}:location_required",
        )


def _normalize_optional_guid(raw: str | None, *, field_name: str) -> str | None:
    if raw is None or str(raw).strip() == "":
        return None
    return _parse_guid(str(raw), field_name=field_name)


def _ensure_client_vehicle_driver(
    db: Session,
    *,
    client_id: str,
    vehicle_id: str | None,
    driver_id: str | None,
) -> None:
    if vehicle_id:
        vehicle = (
            db.query(FleetVehicle.id)
            .filter(repository.id_equals(FleetVehicle.id, vehicle_id), FleetVehicle.client_id == client_id)
            .one_or_none()
        )
        if vehicle is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vehicle_not_found")
    if driver_id:
        driver = (
            db.query(FleetDriver.id)
            .filter(repository.id_equals(FleetDriver.id, driver_id), FleetDriver.client_id == client_id)
            .one_or_none()
        )
        if driver is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="driver_not_found")


def _stop_payload_from_point(
    point: ClientTripPointIn,
    *,
    sequence: int,
    stop_type: LogisticsStopType,
) -> LogisticsStopIn:
    label = _point_label(point)
    return LogisticsStopIn(
        sequence=sequence,
        stop_type=stop_type,
        name=label,
        address_text=label,
        lat=point.lat,
        lon=point.lon,
        planned_arrival_at=point.planned_at,
        planned_departure_at=point.planned_at,
        status=LogisticsStopStatus.PENDING,
        meta={"source": "client_trip_create"},
    )


def _client_trip_stops(payload: ClientTripCreateIn) -> list[LogisticsStopIn]:
    for field_name, point in (("origin", payload.origin), ("destination", payload.destination)):
        _validate_trip_point(point, field_name=field_name, require_location=True)
    for idx, point in enumerate(payload.stops):
        _validate_trip_point(point, field_name=f"stops[{idx}]", require_location=False)

    stops = [_stop_payload_from_point(payload.origin, sequence=0, stop_type=LogisticsStopType.START)]
    stops.extend(
        _stop_payload_from_point(point, sequence=idx, stop_type=LogisticsStopType.WAYPOINT)
        for idx, point in enumerate(payload.stops, start=1)
    )
    stops.append(
        _stop_payload_from_point(
            payload.destination,
            sequence=len(stops),
            stop_type=LogisticsStopType.END,
        )
    )
    return stops


def _trip_meta_from_payload(payload: ClientTripCreateIn) -> dict[str, Any]:
    meta: dict[str, Any] = dict(payload.meta or {})
    if payload.title:
        meta["title"] = payload.title.strip()
    meta["source"] = "client_portal"
    meta["write_owner"] = "processing_core"
    meta["route_preview_owner"] = "logistics_service"
    return meta


def _fuel_report_totals(items: list[dict[str, Any]]) -> dict[str, float | int]:
    return {
        "liters": round(sum(float(item.get("liters") or 0) for item in items), 3),
        "amount": round(sum(float(item.get("amount") or 0) for item in items), 2),
        "tx_count": sum(int(item.get("tx_count") or 0) for item in items),
        "alerts_count": sum(int(item.get("alerts_count") or 0) for item in items),
    }


def _eta_minutes(snapshot: LogisticsETASnapshot | None) -> int | None:
    if snapshot is None:
        return None
    delta = snapshot.eta_end_at - snapshot.computed_at
    return max(0, int(round(delta.total_seconds() / 60)))


def _load_vehicle_driver_maps(
    db: Session,
    orders: list[LogisticsOrder],
) -> tuple[dict[str, FleetVehicle], dict[str, FleetDriver]]:
    vehicle_ids = sorted({str(order.vehicle_id) for order in orders if order.vehicle_id})
    driver_ids = sorted({str(order.driver_id) for order in orders if order.driver_id})
    vehicles = {
        str(item.id): item
        for item in db.query(FleetVehicle).filter(repository.id_in(FleetVehicle.id, vehicle_ids)).all()
    } if vehicle_ids else {}
    drivers = {
        str(item.id): item
        for item in db.query(FleetDriver).filter(repository.id_in(FleetDriver.id, driver_ids)).all()
    } if driver_ids else {}
    return vehicles, drivers


def _route_payload_for_order(db: Session, order: LogisticsOrder) -> tuple[str | None, dict[str, Any] | None]:
    route = repository.get_active_route(db, order_id=str(order.id))
    if route is None:
        latest_routes = repository.list_routes_for_order(db, order_id=str(order.id))
        route = latest_routes[0] if latest_routes else None
    if route is None:
        return None, None
    stops = repository.get_route_stops(db, route_id=str(route.id))
    snapshot = repository.get_latest_route_snapshot(db, route_id=str(route.id))
    latest_eta = repository.get_latest_eta_snapshot(db, order_id=str(order.id))
    payload = {
        "trip_id": str(order.id),
        "stops": [
            {
                "seq": stop.sequence,
                "type": _route_stop_type(stop.stop_type.value),
                "label": stop.name or stop.address_text,
                "lat": stop.lat,
                "lon": stop.lon,
                "planned_at": (stop.planned_arrival_at or stop.planned_departure_at).isoformat()
                if (stop.planned_arrival_at or stop.planned_departure_at)
                else None,
                "actual_at": (stop.actual_arrival_at or stop.actual_departure_at).isoformat()
                if (stop.actual_arrival_at or stop.actual_departure_at)
                else None,
            }
            for stop in stops
        ],
        "distance_km": snapshot.distance_km if snapshot and snapshot.distance_km is not None else route.distance_km,
        "eta_minutes": snapshot.eta_minutes if snapshot and snapshot.eta_minutes is not None else _eta_minutes(latest_eta),
    }
    return str(route.id), payload


def _trip_payload(
    db: Session,
    order: LogisticsOrder,
    *,
    vehicles: dict[str, FleetVehicle],
    drivers: dict[str, FleetDriver],
    include_route: bool,
) -> dict[str, Any]:
    route_id, route_payload = _route_payload_for_order(db, order)
    stops = route_payload["stops"] if route_payload else []
    origin = (
        _format_point(stops[0].get("label"), lat=stops[0].get("lat"), lon=stops[0].get("lon"))
        if stops
        else _format_point(order.origin_text)
    )
    destination = (
        _format_point(stops[-1].get("label"), lat=stops[-1].get("lat"), lon=stops[-1].get("lon"))
        if stops
        else _format_point(order.destination_text)
    )
    vehicle = vehicles.get(str(order.vehicle_id)) if order.vehicle_id else None
    driver = drivers.get(str(order.driver_id)) if order.driver_id else None
    payload = {
        "id": str(order.id),
        "status": _trip_status_for_portal(order.status),
        "title": order.meta.get("title") if isinstance(order.meta, dict) else None,
        "vehicle": (
            {"id": str(vehicle.id), "plate": vehicle.plate_number}
            if vehicle
            else {"id": str(order.vehicle_id), "plate": None} if order.vehicle_id else None
        ),
        "driver": (
            {"id": str(driver.id), "name": driver.full_name}
            if driver
            else {"id": str(order.driver_id), "name": None} if order.driver_id else None
        ),
        "start_planned_at": order.planned_start_at.isoformat() if order.planned_start_at else None,
        "end_planned_at": order.planned_end_at.isoformat() if order.planned_end_at else None,
        "start_actual_at": order.actual_start_at.isoformat() if order.actual_start_at else None,
        "end_actual_at": order.actual_end_at.isoformat() if order.actual_end_at else None,
        "origin": origin,
        "destination": destination,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "route_id": route_id,
        "meta": order.meta,
    }
    if include_route:
        payload["route"] = route_payload
    return payload


def _client_order_or_404(db: Session, *, client_id: str, trip_id: str) -> LogisticsOrder:
    normalized_trip_id = _parse_guid(
        trip_id,
        field_name="trip_id",
        error_status=status.HTTP_404_NOT_FOUND,
        error_detail="trip_not_found",
    )
    order = (
        db.query(LogisticsOrder)
        .filter(repository.id_equals(LogisticsOrder.id, normalized_trip_id), LogisticsOrder.client_id == client_id)
        .one_or_none()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trip_not_found")
    return order


@router.get("/fleet")
def list_fleet(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, ("fleet_vehicles",))
    client_id = _client_id_from_token(token)
    query = db.query(FleetVehicle).filter(FleetVehicle.client_id == client_id)
    if status:
        query = query.filter(FleetVehicle.status == status.strip().upper())
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                FleetVehicle.plate_number.ilike(like),
                FleetVehicle.vin.ilike(like),
                FleetVehicle.brand.ilike(like),
                FleetVehicle.model.ilike(like),
            )
        )
    total = query.count()
    items = query.order_by(FleetVehicle.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": str(item.id),
                "plate": item.plate_number,
                "vin": item.vin,
                "make": item.brand,
                "model": item.model,
                "fuel_type": item.fuel_type_preferred,
                "status": item.status.value,
                "meta": None,
            }
            for item in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/fleet/drivers")
def list_fleet_drivers(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, ("fleet_drivers",))
    client_id = _client_id_from_token(token)
    query = db.query(FleetDriver).filter(FleetDriver.client_id == client_id)
    if status:
        query = query.filter(FleetDriver.status == status.strip().upper())
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(FleetDriver.full_name.ilike(like), FleetDriver.phone.ilike(like)))
    total = query.count()
    items = query.order_by(FleetDriver.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": str(item.id),
                "name": item.full_name,
                "phone": item.phone,
                "status": item.status.value,
                "meta": None,
            }
            for item in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/trips")
def list_trips(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    vehicle_id: str | None = Query(default=None),
    driver_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_READ_TABLES)
    client_id = _client_id_from_token(token)
    query = (
        db.query(LogisticsOrder)
        .outerjoin(FleetVehicle, repository.ids_match(FleetVehicle.id, LogisticsOrder.vehicle_id))
        .outerjoin(FleetDriver, repository.ids_match(FleetDriver.id, LogisticsOrder.driver_id))
        .filter(LogisticsOrder.client_id == client_id)
    )
    filtered_statuses = _trip_filter_statuses(status)
    if filtered_statuses:
        query = query.filter(LogisticsOrder.status.in_(filtered_statuses))
    if vehicle_id:
        query = query.filter(repository.id_equals(LogisticsOrder.vehicle_id, _parse_guid(vehicle_id, field_name="vehicle_id")))
    if driver_id:
        query = query.filter(repository.id_equals(LogisticsOrder.driver_id, _parse_guid(driver_id, field_name="driver_id")))
    parsed_date_from = _parse_datetime(date_from, field_name="date_from")
    parsed_date_to = _parse_datetime(date_to, field_name="date_to")
    if parsed_date_from is not None:
        query = query.filter(LogisticsOrder.planned_start_at >= parsed_date_from)
    if parsed_date_to is not None:
        query = query.filter(LogisticsOrder.planned_start_at <= parsed_date_to)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                LogisticsOrder.id.ilike(like),
                LogisticsOrder.origin_text.ilike(like),
                LogisticsOrder.destination_text.ilike(like),
                FleetVehicle.plate_number.ilike(like),
                FleetDriver.full_name.ilike(like),
            )
        )
    total = query.count()
    items = query.order_by(LogisticsOrder.created_at.desc()).offset(offset).limit(limit).all()
    vehicles, drivers = _load_vehicle_driver_maps(db, items)
    return {
        "items": [_trip_payload(db, item, vehicles=vehicles, drivers=drivers, include_route=False) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/trips/{trip_id}")
def get_trip(
    trip_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_READ_TABLES)
    client_id = _client_id_from_token(token)
    order = _client_order_or_404(db, client_id=client_id, trip_id=trip_id)
    vehicles, drivers = _load_vehicle_driver_maps(db, [order])
    return _trip_payload(db, order, vehicles=vehicles, drivers=drivers, include_route=True)


@router.get("/trips/{trip_id}/route")
def get_trip_route(
    trip_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_READ_TABLES)
    client_id = _client_id_from_token(token)
    order = _client_order_or_404(db, client_id=client_id, trip_id=trip_id)
    _route_id, route_payload = _route_payload_for_order(db, order)
    if route_payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="route_not_available")
    return route_payload


@router.get("/trips/{trip_id}/tracking")
def get_trip_tracking(
    trip_id: str,
    since: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_READ_TABLES)
    client_id = _client_id_from_token(token)
    order = _client_order_or_404(db, client_id=client_id, trip_id=trip_id)
    since_dt = _parse_datetime(since, field_name="since")
    query = db.query(LogisticsTrackingEvent).filter(repository.id_equals(LogisticsTrackingEvent.order_id, order.id))
    if since_dt is not None:
        query = query.filter(LogisticsTrackingEvent.ts >= since_dt)
    events = query.order_by(LogisticsTrackingEvent.ts.asc()).limit(limit).all()
    items = [
        {
            "ts": item.ts.isoformat(),
            "lat": item.lat,
            "lon": item.lon,
            "speed_kmh": item.speed_kmh,
            "heading": item.heading_deg,
            "source": "manual" if isinstance(item.meta, dict) and item.meta.get("source") == "manual" else "gps",
            "accuracy_m": item.meta.get("accuracy_m") if isinstance(item.meta, dict) else None,
        }
        for item in events
        if item.lat is not None and item.lon is not None
    ]
    return {"trip_id": str(order.id), "items": items, "last": items[-1] if items else None}


@router.get("/trips/{trip_id}/position")
def get_trip_position(
    trip_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict | None:
    _require_tables(db, _LOGISTICS_READ_TABLES)
    client_id = _client_id_from_token(token)
    order = _client_order_or_404(db, client_id=client_id, trip_id=trip_id)
    event = repository.get_last_tracking_event(db, order_id=str(order.id))
    if event is None or event.lat is None or event.lon is None:
        return None
    return {
        "ts": event.ts.isoformat(),
        "lat": event.lat,
        "lon": event.lon,
        "speed_kmh": event.speed_kmh,
        "heading": event.heading_deg,
        "source": "manual" if isinstance(event.meta, dict) and event.meta.get("source") == "manual" else "gps",
        "accuracy_m": event.meta.get("accuracy_m") if isinstance(event.meta, dict) else None,
    }


@router.get("/trips/{trip_id}/eta")
def get_trip_eta(
    trip_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_READ_TABLES)
    client_id = _client_id_from_token(token)
    order = _client_order_or_404(db, client_id=client_id, trip_id=trip_id)
    snapshot = repository.get_latest_eta_snapshot(db, order_id=str(order.id))
    if snapshot is None:
        return {
            "trip_id": str(order.id),
            "eta_at": None,
            "eta_minutes": None,
            "updated_at": None,
            "method": None,
            "confidence": None,
        }
    return {
        "trip_id": str(order.id),
        "eta_at": snapshot.eta_end_at.isoformat(),
        "eta_minutes": _eta_minutes(snapshot),
        "updated_at": snapshot.computed_at.isoformat(),
        "method": snapshot.method.value.lower(),
        "confidence": snapshot.eta_confidence,
    }


@router.get("/trips/{trip_id}/deviations")
def get_trip_deviations(
    trip_id: str,
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    type: str | None = Query(default=None),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_READ_TABLES)
    client_id = _client_id_from_token(token)
    order = _client_order_or_404(db, client_id=client_id, trip_id=trip_id)
    since_dt = _parse_datetime(since, field_name="since")
    until_dt = _parse_datetime(until, field_name="until")
    event_types = _deviation_type_filter(type)
    if event_types == ():
        return {"trip_id": str(order.id), "items": []}
    query = db.query(LogisticsDeviationEvent).filter(repository.id_equals(LogisticsDeviationEvent.order_id, order.id))
    if since_dt is not None:
        query = query.filter(LogisticsDeviationEvent.ts >= since_dt)
    if until_dt is not None:
        query = query.filter(LogisticsDeviationEvent.ts <= until_dt)
    if event_types:
        query = query.filter(LogisticsDeviationEvent.event_type.in_(event_types))
    items = query.order_by(LogisticsDeviationEvent.ts.desc()).limit(limit).all()
    return {
        "trip_id": str(order.id),
        "items": [
            {
                "id": str(item.id),
                "ts": item.ts.isoformat(),
                "type": _deviation_type_for_portal(item.event_type),
                "severity": _severity_for_portal(item.severity),
                "title": (
                    item.explain.get("title")
                    if isinstance(item.explain, dict) and item.explain.get("title")
                    else "Unexpected stop"
                    if item.event_type == LogisticsDeviationEventType.UNEXPECTED_STOP
                    else "Route deviation"
                ),
                "details": item.explain.get("details") if isinstance(item.explain, dict) else None,
                "evidence": {
                    **({"lat": item.lat, "lon": item.lon} if item.lat is not None and item.lon is not None else {}),
                    **(
                        {"distance_off_route_km": round(item.distance_from_route_m / 1000, 3)}
                        if item.distance_from_route_m is not None
                        else {}
                    ),
                    **(
                        item.explain.get("evidence")
                        if isinstance(item.explain, dict) and isinstance(item.explain.get("evidence"), dict)
                        else {}
                    ),
                }
                or None,
                "sla_impact": {
                    "trip_id": str(order.id),
                    "impact_level": _impact_level_for_severity(item.severity),
                    "signals": [
                        {
                            "type": _deviation_type_for_portal(item.event_type),
                            "severity": _severity_for_portal(item.severity),
                            "delta_minutes": item.explain.get("delta_minutes")
                            if isinstance(item.explain, dict)
                            else None,
                        }
                    ],
                    "first_response_due_at": item.explain.get("first_response_due_at")
                    if isinstance(item.explain, dict)
                    else None,
                    "resolve_due_at": item.explain.get("resolve_due_at")
                    if isinstance(item.explain, dict)
                    else None,
                    "updated_at": item.ts.isoformat(),
                    "consequence": item.explain.get("consequence") if isinstance(item.explain, dict) else None,
                },
            }
            for item in items
        ],
    }


@router.get("/trips/{trip_id}/sla-impact")
def get_trip_sla_impact(
    trip_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_READ_TABLES)
    client_id = _client_id_from_token(token)
    order = _client_order_or_404(db, client_id=client_id, trip_id=trip_id)
    items = (
        db.query(LogisticsDeviationEvent)
        .filter(repository.id_equals(LogisticsDeviationEvent.order_id, order.id))
        .order_by(LogisticsDeviationEvent.ts.desc())
        .limit(25)
        .all()
    )
    if not items:
        return {
            "trip_id": str(order.id),
            "impact_level": "NONE",
            "signals": [],
            "first_response_due_at": None,
            "resolve_due_at": None,
            "updated_at": None,
            "consequence": None,
        }
    highest = max(items, key=lambda item: _severity_rank(item.severity))
    latest = items[0]
    return {
        "trip_id": str(order.id),
        "impact_level": _impact_level_for_severity(highest.severity),
        "signals": [
            {
                "type": _deviation_type_for_portal(item.event_type),
                "severity": _severity_for_portal(item.severity),
                "delta_minutes": item.explain.get("delta_minutes") if isinstance(item.explain, dict) else None,
            }
            for item in items[:5]
        ],
        "first_response_due_at": latest.explain.get("first_response_due_at") if isinstance(latest.explain, dict) else None,
        "resolve_due_at": latest.explain.get("resolve_due_at") if isinstance(latest.explain, dict) else None,
        "updated_at": latest.ts.isoformat(),
        "consequence": latest.explain.get("consequence") if isinstance(latest.explain, dict) else None,
    }


@router.post("/fuel/linker:run")
def run_fuel_linker(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_READ_TABLES + _LOGISTICS_FUEL_TABLES)
    client_id = _client_id_from_token(token)
    if date_from is None or date_to is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_range_required")
    result = fuel_linker_service.run_linker(db, date_from=date_from, date_to=date_to, client_id=client_id)
    return {"processed": result.processed, "linked": result.linked, "unlinked": result.unlinked, "alerts_created": result.alerts_created}


@router.get("/fuel")
def list_fuel(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_FUEL_TABLES)
    client_id = _client_id_from_token(token)
    query = (
        db.query(
            FuelTransaction.id,
            FuelTransaction.occurred_at,
            FuelTransaction.vehicle_id,
            FuelTransaction.driver_id,
            FuelTransaction.volume_liters,
            FuelTransaction.volume_ml,
            FuelTransaction.amount_total_minor,
            FuelTransaction.merchant_name,
            FuelTransaction.location,
        )
        .filter(FuelTransaction.client_id == client_id)
    )
    if date_from is not None:
        query = query.filter(FuelTransaction.occurred_at >= date_from)
    if date_to is not None:
        query = query.filter(FuelTransaction.occurred_at <= date_to)
    total = query.count()
    items = query.order_by(FuelTransaction.occurred_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": str(item.id),
                "fuel_tx_id": str(item.id),
                "ts": item.occurred_at.isoformat(),
                "vehicle_id": str(item.vehicle_id) if item.vehicle_id else None,
                "driver_id": str(item.driver_id) if item.driver_id else None,
                "liters": float(item.volume_liters) if item.volume_liters is not None else float(item.volume_ml or 0) / 1000,
                "amount": float(item.amount_total_minor or 0),
                "station_name": item.merchant_name or item.location,
                "station": item.location,
            }
            for item in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/fuel/unlinked")
def list_unlinked_fuel(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _require_tables(db, _LOGISTICS_READ_TABLES + _LOGISTICS_FUEL_TABLES)
    client_id = _client_id_from_token(token)
    if date_from is None or date_to is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_range_required")
    return fuel_linker_service.list_unlinked(
        db,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        client_id=client_id,
    )


@router.get("/fuel/alerts")
def list_fuel_alerts(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _require_tables(db, _LOGISTICS_FUEL_TABLES)
    client_id = _client_id_from_token(token)
    if date_from is None or date_to is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_range_required")
    items, _total = fuel_linker_service.fuel_alerts(
        db,
        date_from=date_from,
        date_to=date_to,
        type_=type.strip().upper() if type else None,
        severity=severity.strip().upper() if severity else None,
        status=status.strip().upper() if status else None,
        limit=limit,
        offset=offset,
        client_id=client_id,
    )
    return [
        {
            "id": str(item.id),
            "client_id": item.client_id,
            "trip_id": str(item.trip_id) if item.trip_id else None,
            "fuel_tx_id": str(item.fuel_tx_id),
            "type": item.type.value,
            "severity": item.severity.value,
            "title": item.title,
            "details": item.details,
            "evidence": item.evidence,
            "status": item.status.value,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]


@router.get("/reports/fuel")
def fuel_report(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    group_by: str = Query(default="trip"),
    period: str | None = Query(default=None),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = period
    _require_tables(db, _LOGISTICS_FUEL_TABLES)
    client_id = _client_id_from_token(token)
    if date_from is None or date_to is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_range_required")
    return fuel_linker_service.fuel_report(
        db,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        client_id=client_id,
    )


@router.get("/trips/{trip_id}/fuel")
def trip_fuel(
    trip_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_FUEL_TABLES + ("logistics_orders",))
    client_id = _client_id_from_token(token)
    _client_order_or_404(db, client_id=client_id, trip_id=trip_id)
    payload = fuel_linker_service.trip_fuel(db, trip_id=trip_id)
    return {
        "trip_id": payload["trip_id"],
        "items": [
            {
                "fuel_tx_id": item["fuel_tx_id"],
                "ts": item["ts"].isoformat(),
                "liters": item["liters"],
                "amount": item["amount"],
                "station": item["station"],
                "score": item["score"],
                "reason": item["reason"].value if hasattr(item["reason"], "value") else item["reason"],
            }
            for item in payload["items"]
        ],
        "totals": payload["totals"],
        "alerts": [
            {
                "id": str(item.id),
                "client_id": item.client_id,
                "trip_id": str(item.trip_id) if item.trip_id else None,
                "fuel_tx_id": str(item.fuel_tx_id),
                "type": item.type.value,
                "severity": item.severity.value,
                "title": item.title,
                "details": item.details,
                "evidence": item.evidence,
                "status": item.status.value,
                "created_at": item.created_at.isoformat(),
            }
            for item in payload["alerts"]
        ],
    }


@router.post("/trips", status_code=status.HTTP_201_CREATED)
def create_trip(
    payload: ClientTripCreateIn,
    request: Request,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_WRITE_TABLES)
    client_id = _client_id_from_token(token)
    tenant_id = resolve_token_tenant_id(token, db=db, client_id=client_id, default=DEFAULT_TENANT_ID)
    vehicle_id = _normalize_optional_guid(payload.vehicle_id, field_name="vehicle_id")
    driver_id = _normalize_optional_guid(payload.driver_id, field_name="driver_id")
    _ensure_client_vehicle_driver(db, client_id=client_id, vehicle_id=vehicle_id, driver_id=driver_id)
    stops = _client_trip_stops(payload)
    request_ctx = request_context_from_request(request, token=token, tenant_id_override=tenant_id)
    planned_start_at = payload.start_planned_at or payload.origin.planned_at
    planned_end_at = payload.end_planned_at or payload.destination.planned_at
    try:
        order = logistics_orders.create_order(
            db,
            tenant_id=tenant_id,
            client_id=client_id,
            order_type=LogisticsOrderType.TRIP,
            status=LogisticsOrderStatus.PLANNED,
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            origin_text=_point_label(payload.origin),
            destination_text=_point_label(payload.destination),
            meta=_trip_meta_from_payload(payload),
            request_ctx=request_ctx,
        )
        order_id = str(order.id)
        route = logistics_routes.create_route(
            db,
            order_id=order_id,
            distance_km=payload.distance_km,
            planned_duration_minutes=payload.planned_duration_minutes,
            request_ctx=request_ctx,
        )
        route_id = str(route.id)
        logistics_routes.upsert_stops(db, route_id=route_id, stops=stops, request_ctx=request_ctx)
        logistics_routes.activate_route(db, route_id=route_id, request_ctx=request_ctx)
    except (LogisticsOrderError, LogisticsRouteError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    order = repository.refresh_by_id(db, order, LogisticsOrder, order_id)
    vehicles, drivers = _load_vehicle_driver_maps(db, [order])
    return _trip_payload(db, order, vehicles=vehicles, drivers=drivers, include_route=True)


@router.get("/fuel/consumption")
def fuel_consumption(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    group_by: str = Query(default="trip"),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_FUEL_TABLES + ("logistics_orders",))
    client_id = _client_id_from_token(token)
    normalized_group_by = group_by.strip().lower()
    if normalized_group_by not in {"trip", "vehicle", "driver"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_fuel_consumption_group_by")
    now = datetime.now(timezone.utc)
    resolved_date_to = date_to or now
    resolved_date_from = date_from or (resolved_date_to - timedelta(days=30))
    if resolved_date_from > resolved_date_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_date_range")
    items = fuel_linker_service.fuel_report(
        db,
        date_from=resolved_date_from,
        date_to=resolved_date_to,
        group_by=normalized_group_by,
        client_id=client_id,
    )
    return {
        "items": items,
        "totals": _fuel_report_totals(items),
        "date_from": resolved_date_from.isoformat(),
        "date_to": resolved_date_to.isoformat(),
        "group_by": normalized_group_by,
        "source": "persisted_fuel_links",
    }


@router.post("/fuel/consumption")
def write_fuel_consumption(
    payload: ClientFuelConsumptionWriteIn,
    request: Request,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_tables(db, _LOGISTICS_WRITE_TABLES)
    client_id = _client_id_from_token(token)
    tenant_id = resolve_token_tenant_id(token, db=db, client_id=client_id, default=DEFAULT_TENANT_ID)
    trip_id = _parse_guid(payload.trip_id, field_name="trip_id")
    order = _client_order_or_404(db, client_id=client_id, trip_id=trip_id)
    idempotency_key = (
        payload.idempotency_key
        or request.headers.get("Idempotency-Key")
        or f"client-fuel:{client_id}:{trip_id}:{payload.distance_km:.3f}:{payload.vehicle_kind}"
    )
    service_payload = {
        "trip_id": trip_id,
        "distance_km": payload.distance_km,
        "vehicle_kind": payload.vehicle_kind,
        "idempotency_key": idempotency_key,
    }
    try:
        result = LogisticsServiceClient().fuel_consumption(service_payload, idempotency_key=idempotency_key)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "fuel_consumption_provider_unavailable",
                "reason": str(exc),
                "retryable": True,
            },
        ) from exc

    request_ctx = request_context_from_request(request, token=token, tenant_id_override=tenant_id)
    audit = AuditService(db).audit(
        event_type="LOGISTICS_FUEL_CONSUMPTION_WRITTEN",
        entity_type="logistics_order",
        entity_id=str(order.id),
        action="LOGISTICS_FUEL_CONSUMPTION_WRITTEN",
        visibility=AuditVisibility.INTERNAL,
        after={
            "client_id": client_id,
            "trip_id": trip_id,
            "request": service_payload,
            "provider_response": result,
        },
        external_refs={
            "logistics_service_request_id": result.get("request_id"),
            "idempotency_key": idempotency_key,
            "provider_mode": result.get("provider_mode"),
        },
        request_ctx=request_ctx,
    )
    db.commit()
    return {
        "ok": True,
        "client_id": client_id,
        "trip_id": trip_id,
        "liters": result.get("liters"),
        "method": result.get("method"),
        "source": "logistics_service",
        "provider_mode": result.get("provider_mode"),
        "sandbox_proof": result.get("sandbox_proof"),
        "last_attempt": result.get("last_attempt"),
        "retryable": result.get("retryable"),
        "request_id": result.get("request_id"),
        "idempotency_key": result.get("idempotency_key") or idempotency_key,
        "idempotency_status": result.get("idempotency_status"),
        "audit_event_id": str(audit.id),
    }
