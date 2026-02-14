from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fuel import FuelStation
from app.models.geo_metrics import GeoStationMetricsDaily

WEB_MERCATOR_MAX_LAT = 85.0511


@dataclass(frozen=True)
class GeoBBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


@dataclass(frozen=True)
class StationAggregate:
    station_id: str
    lat: float
    lon: float
    tx_count: int
    captured_count: int
    declined_count: int
    amount_sum: float
    risk_red_count: int
    risk_yellow_count: int


def mercator_tile_xy(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    lat_clamped = max(-WEB_MERCATOR_MAX_LAT, min(WEB_MERCATOR_MAX_LAT, lat))
    lon_clamped = max(-180.0, min(180.0, lon))
    lat_rad = math.radians(lat_clamped)
    n = 2**zoom

    tile_x = int(math.floor((lon_clamped + 180.0) / 360.0 * n))
    sec_lat = 1.0 / math.cos(lat_rad)
    tile_y = int(math.floor((1.0 - math.log(math.tan(lat_rad) + sec_lat) / math.pi) / 2.0 * n))

    max_tile = n - 1
    return max(0, min(max_tile, tile_x)), max(0, min(max_tile, tile_y))


def query_station_aggregates(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    bbox: GeoBBox,
    risk_zone: str | None = None,
    health_status: str | None = None,
    partner_id: str | None = None,
) -> list[StationAggregate]:
    query = (
        db.query(
            GeoStationMetricsDaily.station_id,
            FuelStation.lat,
            FuelStation.lon,
            func.sum(GeoStationMetricsDaily.tx_count).label("tx_count"),
            func.sum(GeoStationMetricsDaily.captured_count).label("captured_count"),
            func.sum(GeoStationMetricsDaily.declined_count).label("declined_count"),
            func.sum(GeoStationMetricsDaily.amount_sum).label("amount_sum"),
            func.sum(GeoStationMetricsDaily.risk_red_count).label("risk_red_count"),
            func.sum(GeoStationMetricsDaily.risk_yellow_count).label("risk_yellow_count"),
        )
        .join(FuelStation, FuelStation.id == GeoStationMetricsDaily.station_id)
        .filter(GeoStationMetricsDaily.day >= date_from, GeoStationMetricsDaily.day <= date_to)
        .filter(FuelStation.lat.isnot(None), FuelStation.lon.isnot(None))
        .filter(FuelStation.lat >= bbox.min_lat, FuelStation.lat <= bbox.max_lat)
        .filter(FuelStation.lon >= bbox.min_lon, FuelStation.lon <= bbox.max_lon)
        .group_by(GeoStationMetricsDaily.station_id, FuelStation.lat, FuelStation.lon)
    )

    if risk_zone:
        query = query.filter(FuelStation.risk_zone == risk_zone)
    if health_status:
        query = query.filter(FuelStation.health_status == health_status)
    if partner_id:
        query = query.filter(FuelStation.network_id == partner_id)

    rows = query.all()
    return [
        StationAggregate(
            station_id=row.station_id,
            lat=float(row.lat),
            lon=float(row.lon),
            tx_count=int(row.tx_count or 0),
            captured_count=int(row.captured_count or 0),
            declined_count=int(row.declined_count or 0),
            amount_sum=float(row.amount_sum or 0),
            risk_red_count=int(row.risk_red_count or 0),
            risk_yellow_count=int(row.risk_yellow_count or 0),
        )
        for row in rows
    ]


def aggregate_to_tiles(stations: list[StationAggregate], *, zoom: int, metric: str) -> list[dict[str, int | float]]:
    metric_getters = {
        "tx_count": lambda s: s.tx_count,
        "captured_count": lambda s: s.captured_count,
        "declined_count": lambda s: s.declined_count,
        "amount_sum": lambda s: s.amount_sum,
        "risk_red_count": lambda s: s.risk_red_count,
        "risk_yellow_count": lambda s: s.risk_yellow_count,
    }
    metric_getter = metric_getters[metric]

    grouped: dict[tuple[int, int], float] = defaultdict(float)
    for station in stations:
        tile_x, tile_y = mercator_tile_xy(station.lat, station.lon, zoom)
        grouped[(tile_x, tile_y)] += float(metric_getter(station))

    return [
        {
            "tile_x": tile_x,
            "tile_y": tile_y,
            "value": int(value) if float(value).is_integer() else value,
        }
        for (tile_x, tile_y), value in grouped.items()
    ]
