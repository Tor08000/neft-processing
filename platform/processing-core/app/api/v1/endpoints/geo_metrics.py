from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.geo import (
    GeoMetricEnum,
    GeoStationOverlayItem,
    GeoStationOverlayMetricEnum,
    GeoStationsMetricsResponse,
    GeoStationsOverlayResponse,
)
from app.services.geo_analytics import GeoBBox as ServiceGeoBBox
from app.services.geo_analytics import query_station_overlay_points
from app.services.geo_metrics import fetch_top_station_metrics

router = APIRouter(prefix="/api/v1/geo/stations", tags=["geo"])


@router.get("/metrics", response_model=GeoStationsMetricsResponse)
def get_geo_stations_metrics(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    metric: GeoMetricEnum = Query(default=GeoMetricEnum.TX_COUNT),
    limit: int = Query(default=20, ge=1, le=200),
    partner_id: int | None = Query(
        default=None
    ),  # reserved for future station->partner relationship
    risk_zone: str | None = Query(default=None),
    health_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> GeoStationsMetricsResponse:
    del partner_id
    now_day = datetime.now(tz=timezone.utc).date()
    parsed_from = (
        datetime.strptime(date_from, "%Y-%m-%d").date()
        if date_from
        else (now_day - timedelta(days=7))
    )
    parsed_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else now_day

    items = fetch_top_station_metrics(
        db,
        date_from=parsed_from,
        date_to=parsed_to,
        metric=metric.value,
        limit=limit,
        risk_zone=risk_zone,
        health_status=health_status,
    )

    return GeoStationsMetricsResponse(
        date_from=parsed_from,
        date_to=parsed_to,
        metric=metric,
        items=items,
        limit=limit,
    )


@router.get("/overlay", response_model=GeoStationsOverlayResponse)
def get_geo_stations_overlay(
    min_lat: float = Query(..., ge=-90, le=90),
    min_lon: float = Query(..., ge=-180, le=180),
    max_lat: float = Query(..., ge=-90, le=90),
    max_lon: float = Query(..., ge=-180, le=180),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    metric: GeoStationOverlayMetricEnum = Query(
        default=GeoStationOverlayMetricEnum.TX_COUNT
    ),
    limit: int = Query(default=500, ge=1, le=5000),
    partner_id: str | None = Query(default=None),
    risk_zone: str | None = Query(default=None),
    health_status: str | None = Query(default=None),
    min_value: float | None = Query(default=None),
    db: Session = Depends(get_db),
) -> GeoStationsOverlayResponse:
    if min_lat >= max_lat:
        raise HTTPException(status_code=422, detail="min_lat must be less than max_lat")
    if min_lon >= max_lon:
        raise HTTPException(status_code=422, detail="min_lon must be less than max_lon")

    now_day = datetime.now(tz=timezone.utc).date()
    parsed_from = (
        datetime.strptime(date_from, "%Y-%m-%d").date()
        if date_from
        else (now_day - timedelta(days=7))
    )
    parsed_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else now_day

    items = query_station_overlay_points(
        db,
        date_from=parsed_from,
        date_to=parsed_to,
        bbox=ServiceGeoBBox(
            min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon
        ),
        metric=metric.value,
        limit=limit,
        risk_zone=risk_zone,
        health_status=health_status,
        partner_id=partner_id,
        min_value=min_value,
    )

    metric_getters = {
        "tx_count": lambda item: item.tx_count,
        "amount_sum": lambda item: item.amount_sum,
        "declined_count": lambda item: item.declined_count,
        "risk_red_count": lambda item: item.risk_red_count,
        "captured_count": lambda item: item.captured_count,
    }

    value_getter = metric_getters[metric.value]

    response_items = [
        GeoStationOverlayItem(
            station_id=item.station_id,
            name=item.name,
            address=item.address,
            lat=item.lat,
            lon=item.lon,
            value=value_getter(item),
            risk_zone=item.risk_zone,
            health_status=item.health_status,
        )
        for item in items
    ]

    return GeoStationsOverlayResponse(
        date_from=parsed_from,
        date_to=parsed_to,
        metric=metric,
        items=response_items,
        returned=len(response_items),
    )
