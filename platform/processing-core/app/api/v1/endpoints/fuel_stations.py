from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fuel import FuelStation
from app.schemas.fuel import (
    FuelStationNearestItem,
    FuelStationOut,
    FuelStationsNearestMeta,
    FuelStationsNearestMetaQuery,
    FuelStationsNearestResponse,
)
from app.services.fuel.stations import NearestStationsQuery, find_nearest_stations, resolve_station_nav_url

router = APIRouter(
    prefix="/api/v1/fuel/stations",
    tags=["fuel-stations"],
)


@router.get("/nearest", response_model=FuelStationsNearestResponse)
def nearest_fuel_stations_endpoint(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    radius_km: float = Query(default=10.0, gt=0.0),
    limit: int = Query(default=30, gt=0),
    only_with_coords: bool = Query(default=True),
    status: str | None = Query(default=None),
    partner_id: int | None = Query(default=None),
    provider: str = Query(default="google", pattern="^(google|yandex|apple)$"),
    db: Session = Depends(get_db),
) -> FuelStationsNearestResponse:
    radius_clamped = min(max(radius_km, 0.1), 200.0)
    limit_clamped = min(max(limit, 1), 200)

    items = find_nearest_stations(
        db,
        NearestStationsQuery(
            lat=lat,
            lon=lon,
            radius_km=radius_clamped,
            limit=limit_clamped,
            only_with_coords=only_with_coords,
            status=status,
            partner_id=partner_id,
        ),
    )

    payload = [
        FuelStationNearestItem(
            **{
                **FuelStationOut.model_validate(item.station).model_dump(),
                "nav_url": resolve_station_nav_url(item.station, provider=provider),
            },
            distance_km=round(item.distance_km, 3),
        )
        for item in items
    ]

    return FuelStationsNearestResponse(
        items=payload,
        meta=FuelStationsNearestMeta(
            query=FuelStationsNearestMetaQuery(
                lat=lat,
                lon=lon,
                radius_km=radius_clamped,
                limit=limit_clamped,
            ),
            returned=len(payload),
        ),
    )


@router.get("/{station_id}", response_model=FuelStationOut)
def get_fuel_station_endpoint(
    station_id: str,
    db: Session = Depends(get_db),
) -> FuelStationOut:
    station = db.query(FuelStation).filter(FuelStation.id == station_id).one_or_none()
    if station is None:
        raise HTTPException(status_code=404, detail="station_not_found")
    return FuelStationOut.model_validate(station)
