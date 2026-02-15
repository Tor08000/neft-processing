from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import requests
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings
from sqlalchemy import func, tuple_
from sqlalchemy.orm import Session

from app.models.bi import BiClickhouseCursor
from app.models.fuel import FuelStation, FuelTransaction, FuelTransactionStatus
from app.services.geo_analytics import GeoBBox, tile_range_from_bbox

logger = get_logger(__name__)
settings = get_settings()

ZOOMS = [8, 10, 12]


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


class GeoClickhouseError(Exception):
    """Geo ClickHouse operation failed."""


def _sql_str(value: str) -> str:
    return value.replace("'", "''")


def _request(query: str) -> list[dict]:
    endpoint = f"{settings.CLICKHOUSE_URL.rstrip('/')}/"
    response = requests.post(
        endpoint,
        params={"database": settings.CLICKHOUSE_DB, "query": f"{query} FORMAT JSONEachRow"},
        timeout=30,
    )
    if response.status_code >= 400:
        raise GeoClickhouseError(response.text)
    lines = [line for line in response.text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _execute(query: str) -> None:
    endpoint = f"{settings.CLICKHOUSE_URL.rstrip('/')}/"
    response = requests.post(
        endpoint,
        params={"database": settings.CLICKHOUSE_DB, "query": query},
        timeout=30,
    )
    if response.status_code >= 400:
        raise GeoClickhouseError(response.text)


def _insert_rows(table: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    endpoint = f"{settings.CLICKHOUSE_URL.rstrip('/')}/"
    payload = "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n"
    response = requests.post(
        endpoint,
        params={"database": settings.CLICKHOUSE_DB, "query": f"INSERT INTO {table} FORMAT JSONEachRow"},
        data=payload.encode("utf-8"),
        timeout=30,
    )
    if response.status_code >= 400:
        raise GeoClickhouseError(response.text)
    return len(rows)


def clickhouse_geo_enabled() -> bool:
    return settings.GEO_ANALYTICS_BACKEND.lower() == "clickhouse"


def clickhouse_ping() -> bool:
    try:
        response = requests.get(f"{settings.CLICKHOUSE_URL.rstrip('/')}/ping", timeout=5)
        return response.status_code < 400 and response.text.strip() == "Ok."
    except Exception:  # noqa: BLE001
        return False


def _load_cursor(db: Session, dataset: str) -> BiClickhouseCursor | None:
    return db.query(BiClickhouseCursor).filter(BiClickhouseCursor.dataset == dataset).one_or_none()


def _save_cursor(db: Session, dataset: str, last_id: str | None, last_occurred_at: datetime | None) -> None:
    cursor = _load_cursor(db, dataset)
    if cursor is None:
        cursor = BiClickhouseCursor(dataset=dataset)
        db.add(cursor)
    cursor.last_id = last_id
    cursor.last_occurred_at = last_occurred_at
    db.flush()


def sync_dim_stations(db: Session, *, batch_size: int = 5000) -> int:
    dataset = "geo_dim_stations"
    cursor = _load_cursor(db, dataset)

    updated_at_expr = func.greatest(
        FuelStation.created_at,
        func.coalesce(FuelStation.health_updated_at, FuelStation.created_at),
        func.coalesce(FuelStation.risk_zone_updated_at, FuelStation.created_at),
    )

    query = (
        db.query(
            FuelStation.id,
            FuelStation.name,
            FuelStation.city,
            FuelStation.lat,
            FuelStation.lon,
            FuelStation.network_id,
            FuelStation.risk_zone,
            FuelStation.health_status,
            updated_at_expr.label("updated_at"),
        )
        .filter(FuelStation.lat.isnot(None), FuelStation.lon.isnot(None))
        .order_by(updated_at_expr.asc(), FuelStation.id.asc())
    )

    if cursor and cursor.last_occurred_at:
        if cursor.last_id:
            query = query.filter(tuple_(updated_at_expr, FuelStation.id) > (cursor.last_occurred_at, cursor.last_id))
        else:
            query = query.filter(updated_at_expr > cursor.last_occurred_at)

    rows = query.limit(batch_size).all()
    payload = [
        {
            "station_id": str(item.id),
            "name": item.name or "",
            "address": item.city or "",
            "lat": float(item.lat),
            "lon": float(item.lon),
            "partner_id": str(item.network_id) if item.network_id else None,
            "risk_zone": item.risk_zone or "",
            "health_status": item.health_status or "",
            "updated_at": item.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for item in rows
    ]

    synced = _insert_rows("dim_stations", payload)
    if rows:
        last = rows[-1]
        _save_cursor(db, dataset, str(last.id), last.updated_at)
    return synced


def _to_amount(transaction: FuelTransaction) -> Decimal:
    if transaction.amount is not None:
        return Decimal(str(transaction.amount))
    if transaction.amount_total_minor is not None:
        return (Decimal(transaction.amount_total_minor) / Decimal("100")).quantize(Decimal("0.01"))
    return Decimal("0")


def _to_liters(transaction: FuelTransaction) -> Decimal:
    if transaction.volume_liters is not None:
        return Decimal(str(transaction.volume_liters))
    if transaction.volume_ml is not None:
        return (Decimal(transaction.volume_ml) / Decimal("1000")).quantize(Decimal("0.001"))
    return Decimal("0")


def _risk_tags(transaction: FuelTransaction) -> set[str]:
    meta = transaction.meta or {}
    if not isinstance(meta, dict):
        return set()
    tags = meta.get("risk_tags") or []
    if not isinstance(tags, list):
        return set()
    return {str(tag) for tag in tags}


def sync_raw_fuel_events(db: Session, *, batch_size: int = 10000) -> int:
    dataset = "geo_raw_fuel_events"
    cursor = _load_cursor(db, dataset)

    query = db.query(FuelTransaction).order_by(FuelTransaction.occurred_at.asc(), FuelTransaction.id.asc())
    if cursor and cursor.last_occurred_at:
        if cursor.last_id:
            query = query.filter(tuple_(FuelTransaction.occurred_at, FuelTransaction.id) > (cursor.last_occurred_at, cursor.last_id))
        else:
            query = query.filter(FuelTransaction.occurred_at > cursor.last_occurred_at)

    rows = query.limit(batch_size).all()
    payload = []
    for transaction in rows:
        tags = _risk_tags(transaction)
        status = transaction.status.value if hasattr(transaction.status, "value") else str(transaction.status)
        payload.append(
            {
                "event_id": str(transaction.id),
                "event_ts": transaction.occurred_at.strftime("%Y-%m-%d %H:%M:%S"),
                "station_id": str(transaction.station_id),
                "status": status,
                "amount": float(_to_amount(transaction)),
                "liters": float(_to_liters(transaction)),
                "captured": 1 if transaction.status == FuelTransactionStatus.SETTLED else 0,
                "decline": 1 if transaction.status == FuelTransactionStatus.DECLINED else 0,
                "risk_red": 1 if "STATION_RISK_RED" in tags else 0,
                "risk_yellow": 1 if "STATION_RISK_YELLOW" in tags else 0,
                "tenant_id": int(transaction.tenant_id),
            }
        )

    synced = _insert_rows("raw_fuel_events", payload)
    if rows:
        last = rows[-1]
        _save_cursor(db, dataset, str(last.id), last.occurred_at)
    return synced


def rebuild_health_overlays(*, target_days: list[date] | None = None) -> int:
    days = target_days or [date.today(), date.today() - timedelta(days=1)]
    affected = 0
    for target in days:
        day_literal = target.isoformat()
        zoom_csv = ",".join(str(z) for z in ZOOMS)
        _execute("SET mutations_sync = 1")
        _execute(
            "ALTER TABLE fact_tiles_overlays_day "
            f"DELETE WHERE day = toDate('{_sql_str(day_literal)}') "
            "AND overlay_kind IN ('HEALTH_OFFLINE', 'HEALTH_DEGRADED') "
            f"AND zoom IN ({zoom_csv})"
        )
        _execute(
            f"""
            INSERT INTO fact_tiles_overlays_day
            SELECT
              toDate('{_sql_str(day_literal)}') AS day,
              z AS zoom,
              if(health_status = 'OFFLINE', 'HEALTH_OFFLINE', 'HEALTH_DEGRADED') AS overlay_kind,
              toUInt32(floor(((lon + 180.0) / 360.0) * pow(2, z))) AS tile_x,
              toUInt32(floor((1.0 - (
                log(tan((least(greatest(lat, -85.0511), 85.0511) * pi() / 180.0)) +
                    1.0 / cos((least(greatest(lat, -85.0511), 85.0511) * pi() / 180.0)))
              ) / pi())) / 2.0 * pow(2, z))) AS tile_y,
              toUInt32(count()) AS value
            FROM dim_stations
            ARRAY JOIN [{','.join(str(z) for z in ZOOMS)}] AS z
            WHERE health_status IN ('OFFLINE', 'DEGRADED')
            GROUP BY day, zoom, overlay_kind, tile_x, tile_y
            """
        )
        affected += 1
    return affected


def run_geo_etl(db: Session) -> dict[str, int]:
    if not clickhouse_geo_enabled():
        return {"stations": 0, "events": 0, "health_overlay_days": 0}
    if not clickhouse_ping():
        raise GeoClickhouseError("clickhouse unavailable")

    stations = sync_dim_stations(db)
    events = sync_raw_fuel_events(db)
    overlay_days = rebuild_health_overlays()
    return {"stations": stations, "events": events, "health_overlay_days": overlay_days}


def fetch_top_station_metrics(
    *,
    date_from: date,
    date_to: date,
    metric: str,
    limit: int,
    risk_zone: str | None = None,
    health_status: str | None = None,
) -> list[dict]:
    filters = [f"f.day >= toDate('{date_from.isoformat()}')", f"f.day <= toDate('{date_to.isoformat()}')"]
    if risk_zone:
        filters.append(f"d.risk_zone = '{_sql_str(risk_zone)}'")
    if health_status:
        filters.append(f"d.health_status = '{_sql_str(health_status)}'")

    metric_col = {
        "tx_count": "tx_count",
        "amount_sum": "amount_sum",
        "declined_count": "declined_count",
        "captured_count": "captured_count",
        "risk_red_count": "risk_red_count",
    }[metric]

    rows = _request(
        f"""
        SELECT
          f.station_id,
          any(d.name) AS station_name,
          any(d.address) AS station_address,
          any(d.lat) AS lat,
          any(d.lon) AS lon,
          toInt64(sum(f.tx_count)) AS tx_count,
          toInt64(sum(f.captured_count)) AS captured_count,
          toInt64(sum(f.declined_count)) AS declined_count,
          sum(f.amount_sum) AS amount_sum,
          sum(f.liters_sum) AS liters_sum,
          toInt64(sum(f.risk_red_count)) AS risk_red_count,
          toInt64(sum(f.risk_yellow_count)) AS risk_yellow_count
        FROM fact_station_day f
        INNER JOIN dim_stations d ON d.station_id = f.station_id
        WHERE {' AND '.join(filters)}
        GROUP BY f.station_id
        ORDER BY {metric_col} DESC
        LIMIT {int(limit)}
        """
    )
    return rows


def query_station_overlay_points(
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
    filters = [
        f"f.day >= toDate('{date_from.isoformat()}')",
        f"f.day <= toDate('{date_to.isoformat()}')",
        f"d.lat >= {bbox.min_lat}",
        f"d.lat <= {bbox.max_lat}",
        f"d.lon >= {bbox.min_lon}",
        f"d.lon <= {bbox.max_lon}",
    ]
    if risk_zone:
        filters.append(f"d.risk_zone = '{_sql_str(risk_zone)}'")
    if health_status:
        filters.append(f"d.health_status = '{_sql_str(health_status)}'")
    if partner_id:
        filters.append(f"d.partner_id = '{_sql_str(partner_id)}'")

    value_expr = {
        "tx_count": "sum(f.tx_count)",
        "amount_sum": "sum(f.amount_sum)",
        "declined_count": "sum(f.declined_count)",
        "risk_red_count": "sum(f.risk_red_count)",
        "captured_count": "sum(f.captured_count)",
    }[metric]

    having = f"HAVING {value_expr} >= {float(min_value)}" if min_value is not None else ""

    rows = _request(
        f"""
        SELECT
          f.station_id,
          any(d.name) AS name,
          any(d.address) AS address,
          any(d.lat) AS lat,
          any(d.lon) AS lon,
          any(d.risk_zone) AS risk_zone,
          any(d.health_status) AS health_status,
          toInt64(sum(f.tx_count)) AS tx_count,
          toInt64(sum(f.captured_count)) AS captured_count,
          toInt64(sum(f.declined_count)) AS declined_count,
          sum(f.amount_sum) AS amount_sum,
          toInt64(sum(f.risk_red_count)) AS risk_red_count,
          {value_expr} AS metric_value
        FROM fact_station_day f
        INNER JOIN dim_stations d ON d.station_id = f.station_id
        WHERE {' AND '.join(filters)}
        GROUP BY f.station_id
        {having}
        ORDER BY metric_value DESC
        LIMIT {int(limit)}
        """
    )

    return [
        StationOverlayAggregate(
            station_id=str(item["station_id"]),
            name=item.get("name"),
            address=item.get("address"),
            lat=float(item["lat"]),
            lon=float(item["lon"]),
            risk_zone=item.get("risk_zone"),
            health_status=item.get("health_status"),
            tx_count=int(item.get("tx_count", 0)),
            captured_count=int(item.get("captured_count", 0)),
            declined_count=int(item.get("declined_count", 0)),
            amount_sum=float(item.get("amount_sum", 0)),
            risk_red_count=int(item.get("risk_red_count", 0)),
        )
        for item in rows
    ]


def query_tiles(
    *,
    date_from: date,
    date_to: date,
    zoom: int,
    bbox: GeoBBox,
    metric: str,
) -> list[dict[str, int | float]]:
    metric_col = {
        "tx_count": "tx_count",
        "captured_count": "captured_count",
        "declined_count": "declined_count",
        "amount_sum": "amount_sum",
        "risk_red_count": "risk_red_count",
        "risk_yellow_count": "risk_yellow_count",
    }[metric]
    min_x, max_x, min_y, max_y = tile_range_from_bbox(bbox, zoom)
    rows = _request(
        f"""
        SELECT
          tile_x,
          tile_y,
          sum({metric_col}) AS value
        FROM fact_tiles_day
        WHERE day >= toDate('{date_from.isoformat()}')
          AND day <= toDate('{date_to.isoformat()}')
          AND zoom = {int(zoom)}
          AND tile_x BETWEEN {min_x} AND {max_x}
          AND tile_y BETWEEN {min_y} AND {max_y}
        GROUP BY tile_x, tile_y
        """
    )
    return [{"tile_x": int(r["tile_x"]), "tile_y": int(r["tile_y"]), "value": float(r["value"])} for r in rows]


def query_overlay_tiles(
    *,
    date_from: date,
    date_to: date,
    zoom: int,
    bbox: GeoBBox,
    overlay_kind: str,
) -> list[dict[str, int]]:
    min_x, max_x, min_y, max_y = tile_range_from_bbox(bbox, zoom)
    rows = _request(
        f"""
        SELECT
          tile_x,
          tile_y,
          toInt64(sum(value)) AS value
        FROM fact_tiles_overlays_day
        WHERE day >= toDate('{date_from.isoformat()}')
          AND day <= toDate('{date_to.isoformat()}')
          AND zoom = {int(zoom)}
          AND overlay_kind = '{_sql_str(overlay_kind)}'
          AND tile_x BETWEEN {min_x} AND {max_x}
          AND tile_y BETWEEN {min_y} AND {max_y}
        GROUP BY tile_x, tile_y
        """
    )
    return [{"tile_x": int(r["tile_x"]), "tile_y": int(r["tile_y"]), "value": int(r["value"])} for r in rows]


__all__ = [
    "GeoClickhouseError",
    "StationOverlayAggregate",
    "clickhouse_geo_enabled",
    "clickhouse_ping",
    "fetch_top_station_metrics",
    "query_overlay_tiles",
    "query_station_overlay_points",
    "query_tiles",
    "run_geo_etl",
]
