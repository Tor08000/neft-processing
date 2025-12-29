from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.admin.fleet_intelligence import (
    FleetDriverScoreOut,
    FleetInsightOut,
    FleetStationTrustOut,
    FleetVehicleEfficiencyOut,
)
from app.services.explain import sources as explain_sources
from app.services.fleet_intelligence import actionable
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


@router.get("/insights/drivers", response_model=list[FleetInsightOut])
def list_driver_insights(
    *,
    client_id: str = Query(...),
    window_days: int = Query(7, ge=1),
    db: Session = Depends(get_db),
) -> list[FleetInsightOut]:
    items = repository.list_latest_driver_scores_by_client(db, client_id=client_id, window_days=window_days)
    insights = []
    for item in items:
        payload = actionable.build_fleet_insight_payload(driver_scores=[item])
        if payload:
            insights.append(FleetInsightOut.model_validate(payload))
    return insights


@router.get("/insights/vehicles", response_model=list[FleetInsightOut])
def list_vehicle_insights(
    *,
    client_id: str = Query(...),
    window_days: int = Query(7, ge=1),
    db: Session = Depends(get_db),
) -> list[FleetInsightOut]:
    items = repository.list_latest_vehicle_scores_by_client(db, client_id=client_id, window_days=window_days)
    insights = []
    for item in items:
        payload = actionable.build_fleet_insight_payload(vehicle_scores=[item])
        if payload:
            insights.append(FleetInsightOut.model_validate(payload))
    return insights


@router.get("/insights/stations", response_model=list[FleetInsightOut])
def list_station_insights(
    *,
    tenant_id: int = Query(..., ge=1),
    window_days: int = Query(7, ge=1),
    db: Session = Depends(get_db),
) -> list[FleetInsightOut]:
    items = repository.list_latest_station_scores_by_tenant(db, tenant_id=tenant_id, window_days=window_days)
    insights = []
    for item in items:
        payload = actionable.build_fleet_insight_payload(station_scores=[item])
        if payload:
            insights.append(FleetInsightOut.model_validate(payload))
    return insights


@router.get("/insights/subject", response_model=FleetInsightOut | None)
def get_subject_insight(
    *,
    fuel_tx_id: str | None = Query(None),
    window_days: int = Query(7, ge=1),
    db: Session = Depends(get_db),
) -> FleetInsightOut | None:
    if not fuel_tx_id:
        return None
    tx = explain_sources.get_fuel_tx(db, fuel_tx_id=fuel_tx_id)
    if not tx:
        return None
    payload = explain_sources.build_fleet_insight_section(
        db,
        tenant_id=tx.tenant_id,
        client_id=tx.client_id,
        driver_id=str(tx.driver_id) if tx.driver_id else None,
        vehicle_id=str(tx.vehicle_id) if tx.vehicle_id else None,
        station_id=str(tx.station_id) if tx.station_id else None,
        window_days=window_days,
    )
    return FleetInsightOut.model_validate(payload) if payload else None


__all__ = ["router"]
