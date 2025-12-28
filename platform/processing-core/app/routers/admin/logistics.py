from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.logistics import LogisticsETASnapshotOut, LogisticsNavigatorExplainOut, LogisticsRouteSnapshotOut
from app.services.audit_service import request_context_from_request
from app.services.logistics import eta, repository

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


@router.get("/routes/{route_id}/navigator", response_model=LogisticsRouteSnapshotOut)
def get_route_navigator_snapshot(
    route_id: str,
    db: Session = Depends(get_db),
) -> LogisticsRouteSnapshotOut:
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
    route = repository.get_route(db, route_id=route_id)
    if not route:
        raise HTTPException(status_code=404, detail="route_not_found")
    snapshot = repository.get_latest_route_snapshot(db, route_id=route_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="navigator_snapshot_not_found")
    explains = repository.list_navigator_explains(db, route_snapshot_id=str(snapshot.id))
    return [LogisticsNavigatorExplainOut.model_validate(explain) for explain in explains]
