from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

import requests
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings
from sqlalchemy.orm import Session

from app.models.fuel import FuelStation, FuelStationPrice
from app.models.operation import Operation, OperationStatus
from app.models.station_elasticity import StationElasticity

logger = get_logger(__name__)
settings = get_settings()

MIN_PRICE_CHANGE_PCT = 0.5
MIN_VOLUME_LITERS = 2000.0
MIN_VOLUME_TX = 50
EPSILON = 1e-9


@dataclass(frozen=True)
class PricePeriod:
    station_id: str
    product_code: str
    price: float
    start_ts: datetime
    end_ts: datetime


def _ch_enabled() -> bool:
    return settings.GEO_ANALYTICS_BACKEND.lower() == "clickhouse"


def _ch_query(query: str) -> list[dict]:
    response = requests.post(
        f"{settings.CLICKHOUSE_URL.rstrip('/')}/",
        params={"database": settings.CLICKHOUSE_DB, "query": f"{query} FORMAT JSONEachRow"},
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def _ch_ping() -> bool:
    try:
        response = requests.get(f"{settings.CLICKHOUSE_URL.rstrip('/')}/ping", timeout=5)
        return response.status_code < 400 and response.text.strip() == "Ok."
    except Exception:
        return False


def _ch_exec(query: str) -> None:
    response = requests.post(
        f"{settings.CLICKHOUSE_URL.rstrip('/')}/",
        params={"database": settings.CLICKHOUSE_DB, "query": query},
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)


def _to_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace(" ", "T"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def detect_product_dimension() -> bool:
    if not _ch_enabled() or not _ch_ping():
        return False
    try:
        rows = _ch_query("DESCRIBE TABLE neft_geo.raw_fuel_events")
    except Exception:
        logger.exception("commercial.elasticity_product_dim_detect_failed")
        return False
    cols = {str(row.get("name", "")).lower() for row in rows}
    return "product_code" in cols


def detect_liters_dimension() -> bool:
    if not _ch_enabled() or not _ch_ping():
        return False
    try:
        rows = _ch_query("DESCRIBE TABLE neft_geo.raw_fuel_events")
    except Exception:
        logger.exception("commercial.elasticity_liters_dim_detect_failed")
        return False
    cols = {str(row.get("name", "")).lower() for row in rows}
    return "liters" in cols


def _ensure_ch_table() -> None:
    if not _ch_enabled() or not _ch_ping():
        return
    _ch_exec(
        """
        CREATE TABLE IF NOT EXISTS neft_geo.fact_station_elasticity (
            station_id UInt64,
            product_code LowCardinality(String) DEFAULT '',
            window_days UInt16,
            elasticity_score Float64,
            elasticity_abs Float64,
            confidence_score Float64,
            sample_points UInt32,
            total_volume Float64,
            updated_at DateTime,
            notes LowCardinality(String)
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (station_id, product_code, window_days)
        """
    )


def _load_price_periods(db: Session, window_start: datetime) -> list[PricePeriod]:
    now = datetime.now(tz=timezone.utc)
    rows = (
        db.query(
            FuelStationPrice.station_id,
            FuelStationPrice.product_code,
            FuelStationPrice.price,
            FuelStationPrice.valid_from,
            FuelStationPrice.updated_at,
        )
        .filter(
            FuelStationPrice.status == "ACTIVE",
            FuelStationPrice.price.isnot(None),
        )
        .order_by(FuelStationPrice.station_id, FuelStationPrice.product_code, FuelStationPrice.valid_from, FuelStationPrice.updated_at)
        .all()
    )

    grouped: dict[tuple[str, str], list] = defaultdict(list)
    for row in rows:
        grouped[(str(row.station_id), str(row.product_code or ""))].append(row)

    periods: list[PricePeriod] = []
    for (station_id, product_code), series in grouped.items():
        starts: list[tuple[datetime, float]] = []
        for row in series:
            start_ts = row.valid_from or row.updated_at
            if start_ts is None:
                continue
            starts.append((_to_datetime(start_ts), float(row.price)))
        starts.sort(key=lambda item: item[0])
        for idx, (start_ts, price) in enumerate(starts):
            end_ts = starts[idx + 1][0] if idx + 1 < len(starts) else now
            if end_ts <= window_start or start_ts >= now:
                continue
            periods.append(
                PricePeriod(
                    station_id=station_id,
                    product_code=product_code,
                    price=price,
                    start_ts=max(start_ts, window_start),
                    end_ts=min(end_ts, now),
                )
            )
    return periods


def _load_ch_events(window_start: datetime, has_product_dim: bool, use_liters: bool) -> dict[tuple[str, str], list[tuple[datetime, float]]]:
    if not _ch_enabled() or not _ch_ping():
        return {}
    product_select = "ifNull(product_code, '') AS product_code" if has_product_dim else "'' AS product_code"
    volume_expr = "toFloat64(ifNull(liters, 0))" if use_liters else "1.0"
    query = f"""
        SELECT
          toString(station_id) AS station_id,
          {product_select},
          event_ts,
          {volume_expr} AS q
        FROM neft_geo.raw_fuel_events
        WHERE captured = 1
          AND event_ts >= toDateTime('{window_start.strftime('%Y-%m-%d %H:%M:%S')}')
          AND station_id != 0
        ORDER BY station_id, product_code, event_ts
    """
    rows = _ch_query(query)
    grouped: dict[tuple[str, str], list[tuple[datetime, float]]] = defaultdict(list)
    for row in rows:
        key = (str(row.get("station_id", "")), str(row.get("product_code", "")) if has_product_dim else "")
        grouped[key].append((_to_datetime(row["event_ts"]), float(row.get("q") or 0.0)))
    return grouped


def _load_pg_events(db: Session, window_start: datetime, has_product_dim: bool) -> dict[tuple[str, str], list[tuple[datetime, float]]]:
    rows = (
        db.query(Operation)
        .filter(
            Operation.created_at >= window_start,
            Operation.fuel_station_id.isnot(None),
            Operation.status == OperationStatus.CAPTURED,
        )
        .all()
    )
    grouped: dict[tuple[str, str], list[tuple[datetime, float]]] = defaultdict(list)
    for op in rows:
        amount = float(op.quantity) if op.quantity is not None and float(op.quantity) > 0 else 1.0
        grouped[(str(op.fuel_station_id), str(op.product_code or "") if has_product_dim else "")].append((_to_datetime(op.created_at), amount))
    return grouped


def compute_period_elasticity(prev_price: float, cur_price: float, prev_q: float, cur_q: float) -> float | None:
    if prev_price <= 0:
        return None
    dp = (cur_price - prev_price) / max(prev_price, EPSILON)
    if abs(dp) < (MIN_PRICE_CHANGE_PCT / 100.0):
        return None
    dq = (cur_q - prev_q) / max(prev_q, EPSILON)
    return dq / dp


def _calculate_elasticity(
    periods: list[PricePeriod],
    events: dict[tuple[str, str], list[tuple[datetime, float]]],
    has_product_dim: bool,
    use_liters: bool,
) -> list[dict]:
    by_key: dict[tuple[str, str], list[PricePeriod]] = defaultdict(list)
    for period in periods:
        key = (period.station_id, period.product_code if has_product_dim else "")
        by_key[key].append(period)

    updated = datetime.now(tz=timezone.utc)
    output: list[dict] = []
    for (station_id, product_code), station_periods in by_key.items():
        sorted_periods = sorted(station_periods, key=lambda p: p.start_ts)
        event_series = events.get((station_id, product_code), [])

        demand_series: list[tuple[PricePeriod, float, int]] = []
        for period in sorted_periods:
            q = 0.0
            tx = 0
            for event_ts, volume in event_series:
                if period.start_ts <= event_ts < period.end_ts:
                    q += volume
                    tx += 1
            demand_series.append((period, q, tx))

        eis: list[float] = []
        total_volume = sum(q for _, q, _ in demand_series)
        max_dp_pct = 0.0
        low_volume = False
        for idx in range(1, len(demand_series)):
            prev_period, q_prev, tx_prev = demand_series[idx - 1]
            cur_period, q_cur, _ = demand_series[idx]
            prev_volume_threshold = MIN_VOLUME_LITERS if use_liters else MIN_VOLUME_TX
            prev_observed = q_prev if use_liters else float(tx_prev)
            if prev_observed < prev_volume_threshold:
                low_volume = True
                continue

            dp_pct = abs((cur_period.price - prev_period.price) / max(prev_period.price, EPSILON)) * 100.0
            max_dp_pct = max(max_dp_pct, dp_pct)
            elasticity = compute_period_elasticity(prev_period.price, cur_period.price, q_prev, q_cur)
            if elasticity is not None:
                eis.append(elasticity)

        sample_points = len(eis)
        base_conf = min(1.0, sample_points / 5.0)
        if total_volume < (MIN_VOLUME_LITERS if use_liters else MIN_VOLUME_TX):
            base_conf *= 0.6
        if max_dp_pct < 1.0:
            base_conf *= 0.7

        note = "OK"
        if not has_product_dim:
            note = "PRODUCT_DIM_MISSING"
        if sample_points == 0 and max_dp_pct < MIN_PRICE_CHANGE_PCT:
            note = "INSUFFICIENT_VARIATION"
        if low_volume and total_volume < (MIN_VOLUME_LITERS if use_liters else MIN_VOLUME_TX):
            note = "INSUFFICIENT_VOLUME"

        output.append(
            {
                "station_id": station_id,
                "product_code": product_code if has_product_dim else "",
                "elasticity_score": float(median(eis)) if eis else 0.0,
                "elasticity_abs": float(median(abs(x) for x in eis)) if eis else 0.0,
                "confidence_score": min(1.0, max(0.0, base_conf)),
                "sample_points": sample_points,
                "total_volume": total_volume,
                "updated_at": updated,
                "notes": note,
            }
        )
    return output


def _to_uint64(station_id: str) -> int:
    return int(float(station_id))


def elasticity_compute(db: Session, window_days: int = 90) -> dict[str, object]:
    window_start = datetime.now(tz=timezone.utc) - timedelta(days=window_days)
    has_product_dim = detect_product_dimension()
    use_liters = detect_liters_dimension()
    _ensure_ch_table()

    periods = _load_price_periods(db, window_start=window_start)
    events = _load_ch_events(window_start=window_start, has_product_dim=has_product_dim, use_liters=use_liters)
    if not events:
        events = _load_pg_events(db, window_start=window_start, has_product_dim=has_product_dim)

    rows = _calculate_elasticity(periods, events, has_product_dim, use_liters)

    db.query(StationElasticity).filter(StationElasticity.window_days == window_days).delete()
    for row in rows:
        db.add(StationElasticity(window_days=window_days, **row))
    db.commit()

    if _ch_enabled() and _ch_ping() and rows:
        serializable_rows = []
        for row in rows:
            try:
                station_id_uint = _to_uint64(str(row["station_id"]))
            except Exception:
                continue
            serializable_rows.append(
                {
                    **row,
                    "station_id": station_id_uint,
                    "window_days": window_days,
                    "updated_at": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        if serializable_rows:
            payload = "\n".join(json.dumps(item, separators=(",", ":")) for item in serializable_rows) + "\n"
            try:
                requests.post(
                    f"{settings.CLICKHOUSE_URL.rstrip('/')}/",
                    params={"database": settings.CLICKHOUSE_DB, "query": "INSERT INTO neft_geo.fact_station_elasticity FORMAT JSONEachRow"},
                    data=payload.encode("utf-8"),
                    timeout=30,
                ).raise_for_status()
            except Exception:
                logger.exception("commercial.elasticity_clickhouse_write_failed")

    logger.info("commercial.elasticity_computed window_days=%s stations=%s has_product_dim=%s", window_days, len(rows), has_product_dim)
    return {"window_days": window_days, "has_product_dim": has_product_dim, "rows": len(rows)}


def fetch_station_elasticity(
    db: Session,
    *,
    window_days: int,
    metric: str,
    order: str,
    limit: int,
    partner_id: str | None,
    risk_zone: str | None,
    health_status: str | None,
    station_id: str | None = None,
) -> list[dict]:
    query = (
        db.query(
            StationElasticity,
            FuelStation.name.label("station_name"),
            FuelStation.city.label("station_address"),
            FuelStation.lat,
            FuelStation.lon,
        )
        .join(FuelStation, FuelStation.id == StationElasticity.station_id)
        .filter(StationElasticity.window_days == window_days)
    )
    if partner_id:
        query = query.filter(FuelStation.network_id == partner_id)
    if risk_zone:
        query = query.filter(FuelStation.risk_zone == risk_zone)
    if health_status:
        query = query.filter(FuelStation.health_status == health_status)
    if station_id:
        query = query.filter(StationElasticity.station_id == station_id)

    rows = query.all()
    items = []
    for elasticity, station_name, station_address, lat, lon in rows:
        items.append(
            {
                "station_id": str(elasticity.station_id),
                "station_name": station_name,
                "station_address": station_address,
                "lat": lat,
                "lon": lon,
                "product_code": elasticity.product_code,
                "window_days": elasticity.window_days,
                "elasticity_score": elasticity.elasticity_score,
                "elasticity_abs": elasticity.elasticity_abs,
                "confidence_score": elasticity.confidence_score,
                "sample_points": elasticity.sample_points,
                "total_volume": elasticity.total_volume,
                "notes": elasticity.notes,
                "updated_at": elasticity.updated_at,
            }
        )
    items.sort(key=lambda x: x.get(metric, 0), reverse=(order == "desc"))
    return items[:limit] if not station_id else items
