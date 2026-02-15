from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.geo import (
    GeoBBox,
    GeoMetricEnum,
    GeoOverlayKindEnum,
    GeoTilesOverlayResponse,
    GeoTilesResponse,
)
from app.services.geo_analytics import GeoBBox as ServiceGeoBBox
from app.services.geo_analytics import query_cached_overlay_tiles, query_cached_tiles
from app.services.geo_clickhouse import (
    GeoClickhouseError,
    clickhouse_geo_enabled,
    clickhouse_ping,
    query_overlay_tiles as query_overlay_tiles_ch,
    query_tiles as query_tiles_ch,
)

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])


@router.get("/tiles", response_model=GeoTilesResponse)
def get_geo_tiles(
    min_lat: float = Query(..., ge=-90, le=90),
    min_lon: float = Query(..., ge=-180, le=180),
    max_lat: float = Query(..., ge=-90, le=90),
    max_lon: float = Query(..., ge=-180, le=180),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    zoom: int = Query(default=10, ge=5, le=14),
    metric: GeoMetricEnum = Query(default=GeoMetricEnum.TX_COUNT),
    limit_tiles: int = Query(default=2000, ge=200, le=20000),
    risk_zone: str | None = Query(default=None),
    health_status: str | None = Query(default=None),
    partner_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> GeoTilesResponse:
    if min_lat >= max_lat:
        raise HTTPException(status_code=422, detail="min_lat must be less than max_lat")
    if min_lon >= max_lon:
        raise HTTPException(status_code=422, detail="min_lon must be less than max_lon")
    if risk_zone or health_status or partner_id:
        raise HTTPException(
            status_code=422,
            detail="risk_zone, health_status and partner_id filters are not supported for cached tiles",
        )

    now_day = datetime.now(tz=timezone.utc).date()
    parsed_from = (
        datetime.strptime(date_from, "%Y-%m-%d").date()
        if date_from
        else (now_day - timedelta(days=7))
    )
    parsed_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else now_day

    bbox = ServiceGeoBBox(
        min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon
    )

    use_clickhouse = clickhouse_geo_enabled() and clickhouse_ping()
    if use_clickhouse:
        try:
            items = query_tiles_ch(
                date_from=parsed_from,
                date_to=parsed_to,
                zoom=zoom,
                bbox=bbox,
                metric=metric.value,
            )
        except GeoClickhouseError:
            items = query_cached_tiles(
                db,
                date_from=parsed_from,
                date_to=parsed_to,
                zoom=zoom,
                bbox=bbox,
                metric=metric.value,
            )
    else:
        items = query_cached_tiles(
            db,
            date_from=parsed_from,
            date_to=parsed_to,
            zoom=zoom,
            bbox=bbox,
            metric=metric.value,
        )
    sorted_items = sorted(items, key=lambda item: float(item["value"]), reverse=True)
    limited_items = sorted_items[:limit_tiles]

    return GeoTilesResponse(
        date_from=parsed_from,
        date_to=parsed_to,
        zoom=zoom,
        metric=metric,
        bbox=GeoBBox(
            min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon
        ),
        items=limited_items,
        returned_tiles=len(limited_items),
        limit_tiles=limit_tiles,
    )


@router.get("/tiles/overlays", response_model=GeoTilesOverlayResponse)
def get_geo_tiles_overlays(
    min_lat: float = Query(..., ge=-90, le=90),
    min_lon: float = Query(..., ge=-180, le=180),
    max_lat: float = Query(..., ge=-90, le=90),
    max_lon: float = Query(..., ge=-180, le=180),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    zoom: int = Query(default=10, ge=5, le=14),
    overlay_kind: GeoOverlayKindEnum = Query(default=GeoOverlayKindEnum.RISK_RED),
    limit_tiles: int = Query(default=2000, ge=200, le=20000),
    db: Session = Depends(get_db),
) -> GeoTilesOverlayResponse:
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

    bbox = ServiceGeoBBox(
        min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon
    )
    use_clickhouse = clickhouse_geo_enabled() and clickhouse_ping()
    if use_clickhouse:
        try:
            items = query_overlay_tiles_ch(
                date_from=parsed_from,
                date_to=parsed_to,
                zoom=zoom,
                bbox=bbox,
                overlay_kind=overlay_kind.value,
            )
        except GeoClickhouseError:
            items = query_cached_overlay_tiles(
                db,
                date_from=parsed_from,
                date_to=parsed_to,
                zoom=zoom,
                bbox=bbox,
                overlay_kind=overlay_kind.value,
            )
    else:
        items = query_cached_overlay_tiles(
            db,
            date_from=parsed_from,
            date_to=parsed_to,
            zoom=zoom,
            bbox=bbox,
            overlay_kind=overlay_kind.value,
        )
    sorted_items = sorted(items, key=lambda item: int(item["value"]), reverse=True)
    limited_items = sorted_items[:limit_tiles]

    return GeoTilesOverlayResponse(
        date_from=parsed_from,
        date_to=parsed_to,
        zoom=zoom,
        overlay_kind=overlay_kind,
        bbox=GeoBBox(
            min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon
        ),
        items=limited_items,
        returned_tiles=len(limited_items),
        limit_tiles=limit_tiles,
    )
