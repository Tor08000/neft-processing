from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.commercial_elasticity import (
    ElasticitySortBy,
    SortOrder,
    StationElasticityDetailResponse,
    StationElasticityListResponse,
)
from app.services.commercial_elasticity import fetch_station_elasticity

router = APIRouter(prefix="/api/v1/commercial/elasticity", tags=["commercial"])


@router.get("/stations", response_model=StationElasticityListResponse)
def list_station_elasticity(
    window_days: int = Query(default=90, ge=30, le=90),
    sort_by: ElasticitySortBy = Query(default=ElasticitySortBy.ELASTICITY_ABS),
    order: SortOrder = Query(default=SortOrder.DESC),
    limit: int = Query(default=50, ge=1, le=200),
    partner_id: str | None = Query(default=None),
    risk_zone: str | None = Query(default=None),
    health_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> StationElasticityListResponse:
    items = fetch_station_elasticity(
        db,
        window_days=window_days,
        metric=sort_by.value,
        order=order.value,
        limit=limit,
        partner_id=partner_id,
        risk_zone=risk_zone,
        health_status=health_status,
    )
    return StationElasticityListResponse(window_days=window_days, sort_by=sort_by, order=order, limit=limit, items=items)


@router.get("/stations/{station_id}", response_model=StationElasticityDetailResponse)
def station_elasticity_detail(
    station_id: str = Path(...),
    window_days: int = Query(default=90, ge=30, le=90),
    db: Session = Depends(get_db),
) -> StationElasticityDetailResponse:
    items = fetch_station_elasticity(
        db,
        window_days=window_days,
        metric=ElasticitySortBy.ELASTICITY_ABS.value,
        order=SortOrder.DESC.value,
        limit=200,
        partner_id=None,
        risk_zone=None,
        health_status=None,
        station_id=station_id,
    )
    return StationElasticityDetailResponse(station_id=station_id, window_days=window_days, items=items)
