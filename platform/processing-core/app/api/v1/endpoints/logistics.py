from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.logistics import (
    LogisticsFuelAlertSeverity,
    LogisticsFuelAlertStatus,
    LogisticsFuelAlertType,
    LogisticsOrderStatus,
)
from app.schemas.logistics import (
    LogisticsFuelAlertOut,
    LogisticsFuelLinkerRunOut,
    LogisticsFuelReportItemOut,
    LogisticsFuelUnlinkedItemOut,
    LogisticsManualFuelLinkIn,
    LogisticsTripFuelOut,
    LogisticsETASnapshotOut,
    LogisticsOrderCreate,
    LogisticsOrderOut,
    LogisticsRouteCreate,
    LogisticsRouteDetail,
    LogisticsRouteOut,
    LogisticsStopIn,
    LogisticsStopOut,
    LogisticsTrackingEventIn,
    LogisticsTrackingEventOut,
)
from app.services.audit_service import request_context_from_request
from app.services.logistics import eta, orders, repository, routes, tracking
from app.services.logistics import fuel_linker_service
from app.services.logistics.orders import LogisticsOrderError
from app.services.logistics.routes import LogisticsRouteError
from app.services.logistics.tracking import LogisticsTrackingError

router = APIRouter(prefix="/api/v1/logistics", tags=["logistics"])


@router.post("/orders", response_model=LogisticsOrderOut)
def create_order_endpoint(
    request: Request,
    payload: LogisticsOrderCreate,
    db: Session = Depends(get_db),
) -> LogisticsOrderOut:
    try:
        order = orders.create_order(
            db,
            tenant_id=payload.tenant_id,
            client_id=payload.client_id,
            order_type=payload.order_type,
            status=payload.status,
            vehicle_id=payload.vehicle_id,
            driver_id=payload.driver_id,
            planned_start_at=payload.planned_start_at,
            planned_end_at=payload.planned_end_at,
            origin_text=payload.origin_text,
            destination_text=payload.destination_text,
            meta=payload.meta,
            request_ctx=request_context_from_request(request),
        )
    except LogisticsOrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LogisticsOrderOut.model_validate(order)


@router.get("/orders", response_model=list[LogisticsOrderOut])
def list_orders_endpoint(
    client_id: str | None = Query(default=None),
    status: LogisticsOrderStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[LogisticsOrderOut]:
    items = repository.list_orders(db, client_id=client_id, status=status, limit=limit, offset=offset)
    return [LogisticsOrderOut.model_validate(item) for item in items]


@router.get("/orders/{order_id}", response_model=LogisticsOrderOut)
def get_order_endpoint(order_id: str, db: Session = Depends(get_db)) -> LogisticsOrderOut:
    order = repository.get_order(db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")
    return LogisticsOrderOut.model_validate(order)


@router.post("/orders/{order_id}/start", response_model=LogisticsOrderOut)
def start_order_endpoint(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> LogisticsOrderOut:
    try:
        order = orders.start_order(db, order_id=order_id, request_ctx=request_context_from_request(request))
    except LogisticsOrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LogisticsOrderOut.model_validate(order)


@router.post("/orders/{order_id}/complete", response_model=LogisticsOrderOut)
def complete_order_endpoint(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> LogisticsOrderOut:
    try:
        order = orders.complete_order(db, order_id=order_id, request_ctx=request_context_from_request(request))
    except LogisticsOrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LogisticsOrderOut.model_validate(order)


@router.post("/orders/{order_id}/cancel", response_model=LogisticsOrderOut)
def cancel_order_endpoint(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> LogisticsOrderOut:
    try:
        order = orders.cancel_order(db, order_id=order_id, request_ctx=request_context_from_request(request))
    except LogisticsOrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LogisticsOrderOut.model_validate(order)


@router.post("/orders/{order_id}/routes", response_model=LogisticsRouteOut)
def create_route_endpoint(
    order_id: str,
    request: Request,
    payload: LogisticsRouteCreate,
    db: Session = Depends(get_db),
) -> LogisticsRouteOut:
    try:
        route = routes.create_route(
            db,
            order_id=order_id,
            distance_km=payload.distance_km,
            planned_duration_minutes=payload.planned_duration_minutes,
            request_ctx=request_context_from_request(request),
        )
    except LogisticsRouteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LogisticsRouteOut.model_validate(route)


@router.post("/routes/{route_id}/activate", response_model=LogisticsRouteOut)
def activate_route_endpoint(
    route_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> LogisticsRouteOut:
    try:
        route = routes.activate_route(db, route_id=route_id, request_ctx=request_context_from_request(request))
    except LogisticsRouteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LogisticsRouteOut.model_validate(route)


@router.post("/routes/{route_id}/stops", response_model=list[LogisticsStopOut])
def upsert_stops_endpoint(
    route_id: str,
    request: Request,
    payload: list[LogisticsStopIn],
    db: Session = Depends(get_db),
) -> list[LogisticsStopOut]:
    try:
        stops = routes.upsert_stops(
            db,
            route_id=route_id,
            stops=payload,
            request_ctx=request_context_from_request(request),
        )
    except LogisticsRouteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [LogisticsStopOut.model_validate(stop) for stop in stops]


@router.get("/routes/{route_id}", response_model=LogisticsRouteDetail)
def get_route_endpoint(route_id: str, db: Session = Depends(get_db)) -> LogisticsRouteDetail:
    route = repository.get_route(db, route_id=route_id)
    if not route:
        raise HTTPException(status_code=404, detail="route_not_found")
    stops = repository.get_route_stops(db, route_id=route_id)
    return LogisticsRouteDetail(
        route=LogisticsRouteOut.model_validate(route),
        stops=[LogisticsStopOut.model_validate(stop) for stop in stops],
    )


@router.post("/orders/{order_id}/tracking", response_model=LogisticsTrackingEventOut)
def ingest_tracking_event_endpoint(
    order_id: str,
    request: Request,
    payload: LogisticsTrackingEventIn,
    db: Session = Depends(get_db),
) -> LogisticsTrackingEventOut:
    try:
        event = tracking.ingest_tracking_event(
            db,
            order_id=order_id,
            payload=payload,
            request_ctx=request_context_from_request(request),
        )
    except LogisticsTrackingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LogisticsTrackingEventOut.model_validate(event)


@router.get("/orders/{order_id}/tracking", response_model=list[LogisticsTrackingEventOut])
def list_tracking_events_endpoint(
    order_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[LogisticsTrackingEventOut]:
    items = repository.list_tracking_events(db, order_id=order_id, limit=limit)
    return [LogisticsTrackingEventOut.model_validate(item) for item in items]


@router.get("/orders/{order_id}/eta", response_model=LogisticsETASnapshotOut)
def get_eta_endpoint(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> LogisticsETASnapshotOut:
    snapshot = eta.get_or_compute_latest_eta(db, order_id=order_id, request_ctx=request_context_from_request(request))
    if not snapshot:
        raise HTTPException(status_code=404, detail="eta_not_available")
    return LogisticsETASnapshotOut.model_validate(snapshot)


@router.post("/fuel/linker:run", response_model=LogisticsFuelLinkerRunOut)
def run_fuel_linker_endpoint(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    db: Session = Depends(get_db),
) -> LogisticsFuelLinkerRunOut:
    result = fuel_linker_service.run_linker(db, date_from=date_from, date_to=date_to)
    return LogisticsFuelLinkerRunOut(
        processed=result.processed,
        linked=result.linked,
        unlinked=result.unlinked,
        alerts_created=result.alerts_created,
    )


@router.get("/fuel/unlinked", response_model=list[LogisticsFuelUnlinkedItemOut])
def list_unlinked_fuel_endpoint(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[LogisticsFuelUnlinkedItemOut]:
    items = fuel_linker_service.list_unlinked(db, date_from=date_from, date_to=date_to, limit=limit, offset=offset)
    return [LogisticsFuelUnlinkedItemOut(**item) for item in items]


@router.get("/trips/{trip_id}/fuel", response_model=LogisticsTripFuelOut)
def trip_fuel_endpoint(trip_id: str, db: Session = Depends(get_db)) -> LogisticsTripFuelOut:
    payload = fuel_linker_service.trip_fuel(db, trip_id=trip_id)
    return LogisticsTripFuelOut(
        trip_id=payload["trip_id"],
        items=payload["items"],
        totals=payload["totals"],
        alerts=[
            LogisticsFuelAlertOut(
                id=str(item.id),
                client_id=item.client_id,
                trip_id=str(item.trip_id) if item.trip_id else None,
                fuel_tx_id=str(item.fuel_tx_id),
                type=item.type.value,
                severity=item.severity.value,
                title=item.title,
                details=item.details,
                evidence=item.evidence,
                status=item.status.value,
                created_at=item.created_at,
            )
            for item in payload["alerts"]
        ],
    )


@router.get("/reports/fuel", response_model=list[LogisticsFuelReportItemOut])
def fuel_report_endpoint(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    group_by: str = Query(default="trip", pattern="^(trip|vehicle|driver)$"),
    period: str = Query(default="day"),
    db: Session = Depends(get_db),
) -> list[LogisticsFuelReportItemOut]:
    _ = period
    rows = fuel_linker_service.fuel_report(db, date_from=date_from, date_to=date_to, group_by=group_by)
    return [LogisticsFuelReportItemOut(**row) for row in rows]


@router.get("/fuel/alerts", response_model=list[LogisticsFuelAlertOut])
def fuel_alerts_endpoint(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    type: LogisticsFuelAlertType | None = Query(default=None),
    severity: LogisticsFuelAlertSeverity | None = Query(default=None),
    status: LogisticsFuelAlertStatus | None = Query(default=LogisticsFuelAlertStatus.OPEN),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[LogisticsFuelAlertOut]:
    items, _total = fuel_linker_service.fuel_alerts(
        db,
        date_from=date_from,
        date_to=date_to,
        type_=type,
        severity=severity,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [
        LogisticsFuelAlertOut(
            id=str(item.id),
            client_id=item.client_id,
            trip_id=str(item.trip_id) if item.trip_id else None,
            fuel_tx_id=str(item.fuel_tx_id),
            type=item.type.value,
            severity=item.severity.value,
            title=item.title,
            details=item.details,
            evidence=item.evidence,
            status=item.status.value,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.post("/fuel/links")
def manual_link_fuel_endpoint(payload: LogisticsManualFuelLinkIn, db: Session = Depends(get_db)) -> dict:
    link = fuel_linker_service.link_manually(db, trip_id=payload.trip_id, fuel_tx_id=payload.fuel_tx_id)
    return {"id": str(link.id), "trip_id": str(link.trip_id), "fuel_tx_id": str(link.fuel_tx_id), "linked_by": link.linked_by.value}


@router.delete("/fuel/links/{fuel_tx_id}")
def manual_unlink_fuel_endpoint(fuel_tx_id: str, db: Session = Depends(get_db)) -> dict:
    fuel_linker_service.unlink(db, fuel_tx_id=fuel_tx_id)
    return {"status": "ok"}
