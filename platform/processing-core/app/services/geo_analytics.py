from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA
from app.models.fuel import FuelStation
from app.models.geo_metrics import (
    GeoStationMetricsDaily,
    GeoTilesDaily,
    GeoTilesDailyOverlay,
)

WEB_MERCATOR_MAX_LAT = 85.0511


GEO_OVERLAY_KINDS = {"RISK_RED", "HEALTH_OFFLINE", "HEALTH_DEGRADED"}


def _table_exists(db: Session, name: str) -> bool:
    try:
        bind = db.get_bind()
        inspector = inspect(bind)
        if inspector.has_table(name, schema=DB_SCHEMA):
            return True
        if bind.dialect.name != "postgresql":
            return inspector.has_table(name)
        return False
    except Exception:
        return False


@dataclass(frozen=True)
class StationOverlayAggregate:
    station_id: str
    name: str | None
    address: str | None
    lat: float
    lon: float
    risk_zone: str | None
    health_status: str | None
    tx_count: int
    captured_count: int
    declined_count: int
    amount_sum: float
    risk_red_count: int


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
    tile_y = int(
        math.floor((1.0 - math.log(math.tan(lat_rad) + sec_lat) / math.pi) / 2.0 * n)
    )

    max_tile = n - 1
    return max(0, min(max_tile, tile_x)), max(0, min(max_tile, tile_y))


def tile_x_from_lon(lon: float, zoom: int) -> int:
    return mercator_tile_xy(0.0, lon, zoom)[0]


def tile_y_from_lat(lat: float, zoom: int) -> int:
    return mercator_tile_xy(lat, 0.0, zoom)[1]


def tile_range_from_bbox(bbox: GeoBBox, zoom: int) -> tuple[int, int, int, int]:
    min_x = tile_x_from_lon(bbox.min_lon, zoom)
    max_x = tile_x_from_lon(bbox.max_lon, zoom)
    min_y = tile_y_from_lat(bbox.max_lat, zoom)
    max_y = tile_y_from_lat(bbox.min_lat, zoom)
    return min(min_x, max_x), max(min_x, max_x), min(min_y, max_y), max(min_y, max_y)


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
    if not _table_exists(db, FuelStation.__table__.name) or not _table_exists(db, GeoStationMetricsDaily.__table__.name):
        return []
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
            func.sum(GeoStationMetricsDaily.risk_yellow_count).label(
                "risk_yellow_count"
            ),
        )
        .join(FuelStation, FuelStation.id == GeoStationMetricsDaily.station_id)
        .filter(
            GeoStationMetricsDaily.day >= date_from,
            GeoStationMetricsDaily.day <= date_to,
        )
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


def aggregate_to_tiles(
    stations: list[StationAggregate], *, zoom: int, metric: str
) -> list[dict[str, int | float]]:
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


def build_geo_tiles_for_day(db: Session, day: date, zoom: int) -> int:
    if not _table_exists(db, FuelStation.__table__.name) or not _table_exists(db, GeoStationMetricsDaily.__table__.name):
        return 0
    rows = (
        db.query(
            GeoStationMetricsDaily.station_id,
            FuelStation.lat,
            FuelStation.lon,
            GeoStationMetricsDaily.tx_count,
            GeoStationMetricsDaily.captured_count,
            GeoStationMetricsDaily.declined_count,
            GeoStationMetricsDaily.amount_sum,
            GeoStationMetricsDaily.liters_sum,
            GeoStationMetricsDaily.risk_red_count,
            GeoStationMetricsDaily.risk_yellow_count,
        )
        .join(FuelStation, FuelStation.id == GeoStationMetricsDaily.station_id)
        .filter(GeoStationMetricsDaily.day == day)
        .filter(FuelStation.lat.isnot(None), FuelStation.lon.isnot(None))
        .all()
    )

    grouped: dict[tuple[int, int], dict[str, int | Decimal]] = defaultdict(
        lambda: {
            "tx_count": 0,
            "captured_count": 0,
            "declined_count": 0,
            "amount_sum": Decimal("0"),
            "liters_sum": Decimal("0"),
            "risk_red_count": 0,
            "risk_yellow_count": 0,
        }
    )

    for row in rows:
        tile_x, tile_y = mercator_tile_xy(float(row.lat), float(row.lon), zoom)
        tile = grouped[(tile_x, tile_y)]
        tile["tx_count"] = int(tile["tx_count"]) + int(row.tx_count or 0)
        tile["captured_count"] = int(tile["captured_count"]) + int(
            row.captured_count or 0
        )
        tile["declined_count"] = int(tile["declined_count"]) + int(
            row.declined_count or 0
        )
        tile["amount_sum"] = Decimal(tile["amount_sum"]) + Decimal(row.amount_sum or 0)
        tile["liters_sum"] = Decimal(tile["liters_sum"]) + Decimal(row.liters_sum or 0)
        tile["risk_red_count"] = int(tile["risk_red_count"]) + int(
            row.risk_red_count or 0
        )
        tile["risk_yellow_count"] = int(tile["risk_yellow_count"]) + int(
            row.risk_yellow_count or 0
        )

    payload = [
        {
            "day": day,
            "zoom": zoom,
            "tile_x": tile_x,
            "tile_y": tile_y,
            **metrics,
        }
        for (tile_x, tile_y), metrics in grouped.items()
    ]

    db.query(GeoTilesDaily).filter(
        GeoTilesDaily.day == day, GeoTilesDaily.zoom == zoom
    ).delete()
    if payload:
        if db.bind and db.bind.dialect.name == "postgresql":
            stmt = pg_insert(GeoTilesDaily).values(payload)
            stmt = stmt.on_conflict_do_update(
                index_elements=["day", "zoom", "tile_x", "tile_y"],
                set_={
                    "tx_count": stmt.excluded.tx_count,
                    "captured_count": stmt.excluded.captured_count,
                    "declined_count": stmt.excluded.declined_count,
                    "amount_sum": stmt.excluded.amount_sum,
                    "liters_sum": stmt.excluded.liters_sum,
                    "risk_red_count": stmt.excluded.risk_red_count,
                    "risk_yellow_count": stmt.excluded.risk_yellow_count,
                    "updated_at": func.now(),
                },
            )
            db.execute(stmt)
        else:
            db.bulk_insert_mappings(GeoTilesDaily, payload)

    db.commit()
    return len(payload)


def geo_tiles_backfill(
    db: Session,
    days: int = 7,
    zooms: list[int] | None = None,
    today: date | None = None,
) -> list[tuple[date, int, int]]:
    zoom_values = zooms or [8, 10, 12]
    anchor = today or date.today()
    rebuilt: list[tuple[date, int, int]] = []
    for delta in range(days):
        target_day = anchor - timedelta(days=delta)
        for zoom in zoom_values:
            tiles_count = build_geo_tiles_for_day(db, day=target_day, zoom=zoom)
            rebuilt.append((target_day, zoom, tiles_count))
    return rebuilt


def query_cached_tiles(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    zoom: int,
    bbox: GeoBBox,
    metric: str,
) -> list[dict[str, int | float]]:
    if not _table_exists(db, GeoTilesDaily.__table__.name):
        return []
    metric_column = {
        "tx_count": GeoTilesDaily.tx_count,
        "captured_count": GeoTilesDaily.captured_count,
        "declined_count": GeoTilesDaily.declined_count,
        "amount_sum": GeoTilesDaily.amount_sum,
        "risk_red_count": GeoTilesDaily.risk_red_count,
        "risk_yellow_count": GeoTilesDaily.risk_yellow_count,
    }[metric]
    min_x, max_x, min_y, max_y = tile_range_from_bbox(bbox, zoom)

    rows = (
        db.query(
            GeoTilesDaily.tile_x,
            GeoTilesDaily.tile_y,
            func.sum(metric_column).label("value"),
        )
        .filter(GeoTilesDaily.day >= date_from, GeoTilesDaily.day <= date_to)
        .filter(GeoTilesDaily.zoom == zoom)
        .filter(GeoTilesDaily.tile_x >= min_x, GeoTilesDaily.tile_x <= max_x)
        .filter(GeoTilesDaily.tile_y >= min_y, GeoTilesDaily.tile_y <= max_y)
        .group_by(GeoTilesDaily.tile_x, GeoTilesDaily.tile_y)
        .all()
    )

    return [
        {
            "tile_x": int(row.tile_x),
            "tile_y": int(row.tile_y),
            "value": (
                int(row.value) if float(row.value).is_integer() else float(row.value)
            ),
        }
        for row in rows
    ]


def build_geo_overlay_tiles_for_day(db: Session, day: date, zoom: int) -> int:
    if not _table_exists(db, FuelStation.__table__.name) or not _table_exists(db, GeoStationMetricsDaily.__table__.name):
        return 0
    risk_rows = (
        db.query(
            FuelStation.lat,
            FuelStation.lon,
            func.sum(GeoStationMetricsDaily.risk_red_count).label("value"),
        )
        .join(FuelStation, FuelStation.id == GeoStationMetricsDaily.station_id)
        .filter(GeoStationMetricsDaily.day == day)
        .filter(FuelStation.lat.isnot(None), FuelStation.lon.isnot(None))
        .group_by(FuelStation.id, FuelStation.lat, FuelStation.lon)
        .all()
    )

    grouped: dict[tuple[int, int, str], int] = defaultdict(int)

    for row in risk_rows:
        tile_x, tile_y = mercator_tile_xy(float(row.lat), float(row.lon), zoom)
        grouped[(tile_x, tile_y, "RISK_RED")] += int(row.value or 0)

    health_rows = (
        db.query(FuelStation.lat, FuelStation.lon, FuelStation.health_status)
        .filter(FuelStation.lat.isnot(None), FuelStation.lon.isnot(None))
        .filter(FuelStation.health_status.in_(["OFFLINE", "DEGRADED"]))
        .all()
    )
    for row in health_rows:
        tile_x, tile_y = mercator_tile_xy(float(row.lat), float(row.lon), zoom)
        if row.health_status == "OFFLINE":
            grouped[(tile_x, tile_y, "HEALTH_OFFLINE")] += 1
        elif row.health_status == "DEGRADED":
            grouped[(tile_x, tile_y, "HEALTH_DEGRADED")] += 1

    payload = [
        {
            "day": day,
            "zoom": zoom,
            "tile_x": tile_x,
            "tile_y": tile_y,
            "overlay_kind": overlay_kind,
            "value": value,
        }
        for (tile_x, tile_y, overlay_kind), value in grouped.items()
    ]

    db.query(GeoTilesDailyOverlay).filter(
        GeoTilesDailyOverlay.day == day, GeoTilesDailyOverlay.zoom == zoom
    ).delete()
    if payload:
        if db.bind and db.bind.dialect.name == "postgresql":
            stmt = pg_insert(GeoTilesDailyOverlay).values(payload)
            stmt = stmt.on_conflict_do_update(
                index_elements=["day", "zoom", "tile_x", "tile_y", "overlay_kind"],
                set_={"value": stmt.excluded.value, "updated_at": func.now()},
            )
            db.execute(stmt)
        else:
            db.bulk_insert_mappings(GeoTilesDailyOverlay, payload)

    db.commit()
    return len(payload)


def geo_overlay_tiles_backfill(
    db: Session,
    days: int = 7,
    zooms: list[int] | None = None,
    today: date | None = None,
) -> list[tuple[date, int, int]]:
    zoom_values = zooms or [8, 10, 12]
    anchor = today or date.today()
    rebuilt: list[tuple[date, int, int]] = []
    for delta in range(days):
        target_day = anchor - timedelta(days=delta)
        for zoom in zoom_values:
            tiles_count = build_geo_overlay_tiles_for_day(db, day=target_day, zoom=zoom)
            rebuilt.append((target_day, zoom, tiles_count))
    return rebuilt


def query_cached_overlay_tiles(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    zoom: int,
    bbox: GeoBBox,
    overlay_kind: str,
) -> list[dict[str, int]]:
    if not _table_exists(db, GeoTilesDailyOverlay.__table__.name):
        return []
    min_x, max_x, min_y, max_y = tile_range_from_bbox(bbox, zoom)

    rows = (
        db.query(
            GeoTilesDailyOverlay.tile_x,
            GeoTilesDailyOverlay.tile_y,
            func.sum(GeoTilesDailyOverlay.value).label("value"),
        )
        .filter(
            GeoTilesDailyOverlay.day >= date_from, GeoTilesDailyOverlay.day <= date_to
        )
        .filter(GeoTilesDailyOverlay.zoom == zoom)
        .filter(GeoTilesDailyOverlay.overlay_kind == overlay_kind)
        .filter(
            GeoTilesDailyOverlay.tile_x >= min_x, GeoTilesDailyOverlay.tile_x <= max_x
        )
        .filter(
            GeoTilesDailyOverlay.tile_y >= min_y, GeoTilesDailyOverlay.tile_y <= max_y
        )
        .group_by(GeoTilesDailyOverlay.tile_x, GeoTilesDailyOverlay.tile_y)
        .all()
    )

    return [
        {"tile_x": int(r.tile_x), "tile_y": int(r.tile_y), "value": int(r.value or 0)}
        for r in rows
    ]


def query_station_overlay_points(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    bbox: GeoBBox,
    metric: str,
    limit: int,
    risk_zone: str | None = None,
    health_status: str | None = None,
    partner_id: str | None = None,
    min_value: float | None = None,
) -> list[StationOverlayAggregate]:
    if not _table_exists(db, FuelStation.__table__.name) or not _table_exists(db, GeoStationMetricsDaily.__table__.name):
        return []
    metric_columns = {
        "tx_count": func.sum(GeoStationMetricsDaily.tx_count),
        "amount_sum": func.sum(GeoStationMetricsDaily.amount_sum),
        "declined_count": func.sum(GeoStationMetricsDaily.declined_count),
        "risk_red_count": func.sum(GeoStationMetricsDaily.risk_red_count),
        "captured_count": func.sum(GeoStationMetricsDaily.captured_count),
    }
    value_expr = metric_columns[metric]

    query = (
        db.query(
            FuelStation.id.label("station_id"),
            FuelStation.name,
            FuelStation.city.label("address"),
            FuelStation.lat,
            FuelStation.lon,
            FuelStation.risk_zone,
            FuelStation.health_status,
            func.sum(GeoStationMetricsDaily.tx_count).label("tx_count"),
            func.sum(GeoStationMetricsDaily.captured_count).label("captured_count"),
            func.sum(GeoStationMetricsDaily.declined_count).label("declined_count"),
            func.sum(GeoStationMetricsDaily.amount_sum).label("amount_sum"),
            func.sum(GeoStationMetricsDaily.risk_red_count).label("risk_red_count"),
            value_expr.label("value"),
        )
        .join(FuelStation, FuelStation.id == GeoStationMetricsDaily.station_id)
        .filter(
            GeoStationMetricsDaily.day >= date_from,
            GeoStationMetricsDaily.day <= date_to,
        )
        .filter(FuelStation.lat.isnot(None), FuelStation.lon.isnot(None))
        .filter(FuelStation.lat >= bbox.min_lat, FuelStation.lat <= bbox.max_lat)
        .filter(FuelStation.lon >= bbox.min_lon, FuelStation.lon <= bbox.max_lon)
        .group_by(
            FuelStation.id,
            FuelStation.name,
            FuelStation.city,
            FuelStation.lat,
            FuelStation.lon,
            FuelStation.risk_zone,
            FuelStation.health_status,
        )
    )

    if risk_zone:
        query = query.filter(FuelStation.risk_zone == risk_zone)
    if health_status:
        query = query.filter(FuelStation.health_status == health_status)
    if partner_id:
        query = query.filter(FuelStation.network_id == partner_id)

    if min_value is not None:
        query = query.having(value_expr >= min_value)

    rows = query.order_by(value_expr.desc()).limit(limit).all()

    return [
        StationOverlayAggregate(
            station_id=str(r.station_id),
            name=r.name,
            address=r.address,
            lat=float(r.lat),
            lon=float(r.lon),
            risk_zone=r.risk_zone,
            health_status=r.health_status,
            tx_count=int(r.tx_count or 0),
            captured_count=int(r.captured_count or 0),
            declined_count=int(r.declined_count or 0),
            amount_sum=float(r.amount_sum or 0),
            risk_red_count=int(r.risk_red_count or 0),
        )
        for r in rows
    ]
