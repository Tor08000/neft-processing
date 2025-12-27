from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.logistics import (
    FuelRouteLinkOut,
    LogisticsDeviationEventOut,
    LogisticsETAAccuracyOut,
    LogisticsETASnapshotOut,
    LogisticsRiskSignalOut,
)
from app.services.audit_service import request_context_from_request
from datetime import datetime, timedelta, timezone

from app.models.logistics import LogisticsOrder, LogisticsOrderStatus
from app.models.fuel import FuelTransaction
from app.models.logistics import FuelRouteLink, LogisticsRiskSignal, LogisticsRiskSignalType
from app.services.logistics import deviation, eta, fuel_linker, repository
from app.services.logistics.defaults import HEALTH_DEFAULTS
from app.services.logistics.metrics import metrics as logistics_metrics

router = APIRouter(prefix="/logistics", tags=["admin", "logistics"])


@router.post("/orders/{order_id}/eta/recompute", response_model=LogisticsETASnapshotOut)
def recompute_eta_endpoint(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
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


@router.get("/orders/{order_id}/deviations", response_model=list[LogisticsDeviationEventOut])
def list_deviations_endpoint(order_id: str, db: Session = Depends(get_db)) -> list[LogisticsDeviationEventOut]:
    items = repository.list_deviation_events(db, order_id=order_id)
    return [LogisticsDeviationEventOut.model_validate(item) for item in items]


@router.get("/orders/{order_id}/eta-accuracy", response_model=list[LogisticsETAAccuracyOut])
def list_eta_accuracy_endpoint(order_id: str, db: Session = Depends(get_db)) -> list[LogisticsETAAccuracyOut]:
    items = repository.list_eta_accuracy(db, order_id=order_id)
    return [LogisticsETAAccuracyOut.model_validate(item) for item in items]


@router.get("/orders/{order_id}/fuel-links", response_model=list[FuelRouteLinkOut])
def list_fuel_links_endpoint(order_id: str, db: Session = Depends(get_db)) -> list[FuelRouteLinkOut]:
    items = repository.list_fuel_links(db, order_id=order_id)
    return [FuelRouteLinkOut.model_validate(item) for item in items]


@router.get("/orders/{order_id}/risk-signals", response_model=list[LogisticsRiskSignalOut])
def list_risk_signals_endpoint(order_id: str, db: Session = Depends(get_db)) -> list[LogisticsRiskSignalOut]:
    items = repository.list_risk_signals(db, order_id=order_id)
    return [LogisticsRiskSignalOut.model_validate(item) for item in items]


@router.get("/health", response_model=dict)
def logistics_health_endpoint(db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=HEALTH_DEFAULTS.tracking_stale_minutes)
    in_progress = (
        db.query(LogisticsOrder)
        .filter(LogisticsOrder.status == LogisticsOrderStatus.IN_PROGRESS)
        .all()
    )
    stale_tracking = 0
    off_route_confirmed = 0
    for order in in_progress:
        last_event = repository.get_last_tracking_event(db, order_id=str(order.id))
        if not last_event or last_event.ts < stale_before:
            stale_tracking += 1
        state = (order.meta or {}).get("deviation_state", {})
        if state.get("status") == "OFF_ROUTE_CONFIRMED":
            off_route_confirmed += 1

    order_vehicle_ids = [order.vehicle_id for order in in_progress if order.vehicle_id]
    fuel_tx_without_link = 0
    if order_vehicle_ids:
        fuel_tx_without_link = (
            db.query(FuelTransaction)
            .filter(FuelTransaction.vehicle_id.in_(order_vehicle_ids))
            .filter(FuelTransaction.id.notin_(select(FuelRouteLink.fuel_tx_id).distinct()))
            .count()
        )

    eta_anomalies = (
        db.query(LogisticsRiskSignal)
        .filter(LogisticsRiskSignal.signal_type == LogisticsRiskSignalType.ETA_ANOMALY)
        .count()
    )

    logistics_metrics.inc("logistics_tracking_stale_total", stale_tracking)
    return {
        "status": "ok",
        "stats": {
            "in_progress_orders": len(in_progress),
            "stale_tracking": stale_tracking,
            "off_route_confirmed": off_route_confirmed,
            "fuel_tx_without_link": fuel_tx_without_link,
            "eta_anomalies": eta_anomalies,
        },
        "metrics": logistics_metrics.counters,
    }


@router.post("/orders/{order_id}/recompute", response_model=dict)
def recompute_order_endpoint(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    order = repository.get_order(db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")

    request_ctx = request_context_from_request(request)
    route = repository.get_active_route(db, order_id=order_id)
    if route:
        events = repository.list_tracking_events(db, order_id=order_id, limit=50)
        for event in reversed(events):
            if event.lat is None or event.lon is None:
                continue
            deviation.check_route_deviation(
                db,
                order=order,
                route=route,
                lat=event.lat,
                lon=event.lon,
                ts=event.ts,
                request_ctx=request_ctx,
            )
    fuel_linker.auto_link_for_order(db, order=order, request_ctx=request_ctx)
    eta.compute_eta_snapshot(db, order_id=order_id, reason="admin_recompute", request_ctx=request_ctx)
    return {"status": "ok"}
