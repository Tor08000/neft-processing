from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.admin.fleet_intelligence import (
    FleetDriverScoreOut,
    FleetStationTrustOut,
    FleetVehicleEfficiencyOut,
)
from app.services.fleet_intelligence import repository

router = APIRouter(prefix="/fleet-intelligence", tags=["admin", "fleet-intelligence"])


@router.get("/drivers", response_model=list[FleetDriverScoreOut])
def list_driver_scores(
    *,
    client_id: str = Query(...),
    window_days: int = Query(7, ge=1),
    db: Session = Depends(get_db),
) -> list[FleetDriverScoreOut]:
    items = repository.list_latest_driver_scores_by_client(db, client_id=client_id, window_days=window_days)
    return [FleetDriverScoreOut.model_validate(item) for item in items]


@router.get("/vehicles", response_model=list[FleetVehicleEfficiencyOut])
def list_vehicle_scores(
    *,
    client_id: str = Query(...),
    window_days: int = Query(7, ge=1),
    db: Session = Depends(get_db),
) -> list[FleetVehicleEfficiencyOut]:
    items = repository.list_latest_vehicle_scores_by_client(db, client_id=client_id, window_days=window_days)
    return [FleetVehicleEfficiencyOut.model_validate(item) for item in items]


@router.get("/stations", response_model=list[FleetStationTrustOut])
def list_station_scores(
    *,
    tenant_id: int = Query(..., ge=1),
    window_days: int = Query(7, ge=1),
    db: Session = Depends(get_db),
) -> list[FleetStationTrustOut]:
    items = repository.list_latest_station_scores_by_tenant(db, tenant_id=tenant_id, window_days=window_days)
    return [FleetStationTrustOut.model_validate(item) for item in items]


__all__ = ["router"]
