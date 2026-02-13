from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.geo import GeoMetricEnum, GeoStationsMetricsResponse
from app.services.geo_metrics import fetch_top_station_metrics

router = APIRouter(prefix="/api/v1/geo/stations", tags=["geo"])


@router.get("/metrics", response_model=GeoStationsMetricsResponse)
def get_geo_stations_metrics(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    metric: GeoMetricEnum = Query(default=GeoMetricEnum.TX_COUNT),
    limit: int = Query(default=20, ge=1, le=200),
    partner_id: int | None = Query(default=None),  # reserved for future station->partner relationship
    risk_zone: str | None = Query(default=None),
    health_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> GeoStationsMetricsResponse:
    del partner_id
    now_day = datetime.now(tz=timezone.utc).date()
    parsed_from = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else (now_day - timedelta(days=7))
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
