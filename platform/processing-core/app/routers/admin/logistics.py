from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin_capability import require_admin_capability
from app.db import get_db
from app.schemas.logistics import (
    LogisticsAdminInspectionOut,
    LogisticsETASnapshotOut,
    LogisticsNavigatorExplainOut,
    LogisticsOrderOut,
    LogisticsRouteOut,
    LogisticsRouteSnapshotOut,
    LogisticsStopOut,
    LogisticsTrackingEventOut,
)
from app.services.audit_service import request_context_from_request
from app.services.logistics import eta, repository

router = APIRouter(
    prefix="/logistics",
    tags=["admin", "logistics"],
    dependencies=[Depends(require_admin_capability("ops"))],
)


@router.post("/orders/{order_id}/eta/recompute", response_model=LogisticsETASnapshotOut)
def recompute_eta_endpoint(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _token: dict = Depends(require_admin_capability("ops", "operate")),
) -> LogisticsETASnapshotOut:
    snapshot = eta.compute_eta_snapshot(
        db,
        order_id=order_id,
        reason="admin_recompute",
        request_ctx=request_context_from_request(request),
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="eta_not_available")
    return LogisticsETASnapshotOut.model_validate(snapshot)


@router.get("/orders/{order_id}/inspection", response_model=LogisticsAdminInspectionOut)
def get_order_inspection(
    order_id: str,
    db: Session = Depends(get_db),
) -> LogisticsAdminInspectionOut:
    order = repository.get_order(db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")

    active_route = repository.get_active_route(db, order_id=order_id)
    routes = repository.list_routes_for_order(db, order_id=order_id)
    inspection_route = active_route or (routes[0] if routes else None)
    active_route_stops = (
        repository.get_route_stops(db, route_id=str(inspection_route.id))
        if inspection_route
        else []
    )
    latest_eta_snapshot = repository.get_latest_eta_snapshot(db, order_id=order_id)
    latest_route_snapshot = (
        repository.get_latest_route_snapshot(db, route_id=str(inspection_route.id))
        if inspection_route
        else None
    )
    navigator_explains = (
        repository.list_navigator_explains(db, route_snapshot_id=str(latest_route_snapshot.id))
        if latest_route_snapshot
        else []
    )
    last_tracking_event = repository.get_last_tracking_event(db, order_id=order_id)

    return LogisticsAdminInspectionOut(
        order=LogisticsOrderOut.model_validate(order),
        active_route=LogisticsRouteOut.model_validate(active_route) if active_route else None,
        routes=[LogisticsRouteOut.model_validate(route) for route in routes],
        active_route_stops=[LogisticsStopOut.model_validate(stop) for stop in active_route_stops],
        latest_eta_snapshot=(
            LogisticsETASnapshotOut.model_validate(latest_eta_snapshot)
            if latest_eta_snapshot
            else None
        ),
        latest_route_snapshot=(
            LogisticsRouteSnapshotOut.model_validate(latest_route_snapshot)
            if latest_route_snapshot
            else None
        ),
        navigator_explains=[
            LogisticsNavigatorExplainOut.model_validate(explain) for explain in navigator_explains
        ],
        tracking_events_count=repository.count_tracking_events(db, order_id=order_id),
        last_tracking_event=(
            LogisticsTrackingEventOut.model_validate(last_tracking_event)
            if last_tracking_event
            else None
        ),
    )


@router.get("/routes/{route_id}/navigator", response_model=LogisticsRouteSnapshotOut)
def get_route_navigator_snapshot(
    route_id: str,
    db: Session = Depends(get_db),
) -> LogisticsRouteSnapshotOut:
    # Admin exposes the latest local snapshot artifact for inspection.
    # This is not a public routing-provider API and carries no external routing ownership.
    route = repository.get_route(db, route_id=route_id)
    if not route:
        raise HTTPException(status_code=404, detail="route_not_found")
    snapshot = repository.get_latest_route_snapshot(db, route_id=route_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="navigator_snapshot_not_found")
    return LogisticsRouteSnapshotOut.model_validate(snapshot)


@router.get("/routes/{route_id}/navigator/explain", response_model=list[LogisticsNavigatorExplainOut])
def list_route_navigator_explains(
    route_id: str,
    db: Session = Depends(get_db),
) -> list[LogisticsNavigatorExplainOut]:
    # Explain records are the companion evidence trail for the local navigator snapshot layer.
    route = repository.get_route(db, route_id=route_id)
    if not route:
        raise HTTPException(status_code=404, detail="route_not_found")
    snapshot = repository.get_latest_route_snapshot(db, route_id=route_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="navigator_snapshot_not_found")
    explains = repository.list_navigator_explains(db, route_snapshot_id=str(snapshot.id))
    return [LogisticsNavigatorExplainOut.model_validate(explain) for explain in explains]
