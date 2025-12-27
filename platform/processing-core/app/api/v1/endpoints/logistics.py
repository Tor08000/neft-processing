from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.logistics import LogisticsOrderStatus
from app.schemas.logistics import (
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
