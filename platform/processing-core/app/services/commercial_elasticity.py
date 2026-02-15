from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

import requests
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings
from sqlalchemy import inspect, literal, text
from sqlalchemy.orm import Session

from app.models.fuel import FuelStation
from app.models.operation import Operation, OperationStatus
from app.models.station_elasticity import StationElasticity

logger = get_logger(__name__)
settings = get_settings()

MIN_PRICE_CHANGE_PCT = 0.5
MIN_VOLUME_THRESHOLD = 200.0
MIN_TX_THRESHOLD = 20


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


def detect_product_dimension() -> bool:
    if not _ch_enabled():
        return False
    try:
        rows = _ch_query("DESCRIBE TABLE neft_geo.raw_fuel_events")
    except Exception:
        logger.exception("commercial.elasticity_product_dim_detect_failed")
        return False
    cols = {str(row.get("name", "")).lower() for row in rows}
    return "product_code" in cols or "product_id" in cols


def _discover_price_source(db: Session) -> tuple[str, bool]:
    inspector = inspect(db.bind)
    table_names = set(inspector.get_table_names())
    for table_name in ("fuel_station_prices", "station_prices", "f3_station_prices"):
        if table_name in table_names:
            cols = {c["name"] for c in inspector.get_columns(table_name)}
            has_product = "product_code" in cols or "product_id" in cols
            return table_name, has_product
    if _ch_enabled():
        try:
            rows = _ch_query(
                """
                SELECT name FROM system.tables
                WHERE database = 'neft_geo' AND name in ('dim_prices', 'f3_station_prices')
                """
            )
            if rows:
                return str(rows[0]["name"]), True
        except Exception:
            logger.exception("commercial.elasticity_price_source_detect_failed")
    return "", False


def _to_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace(" ", "T"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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
            notes LowCardinality(String),
            updated_at DateTime
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (station_id, product_code, window_days)
        """
    )


def _load_price_periods(db: Session, window_start: datetime, has_product_dim: bool) -> list[PricePeriod]:
    table_name, source_has_product = _discover_price_source(db)
    if table_name:
        cols = {c["name"] for c in inspect(db.bind).get_columns(table_name)}
        product_col = "product_code" if "product_code" in cols else ("product_id" if "product_id" in cols else None)
        from_col = "valid_from" if "valid_from" in cols else ("created_at" if "created_at" in cols else "updated_at")
        to_col = "valid_to" if "valid_to" in cols else None

        product_select = f"{product_col} AS product_code" if product_col else "'' AS product_code"
        q = f"SELECT station_id, {product_select}, price, {from_col} AS from_ts"
        if to_col:
            q += f", {to_col} AS to_ts"
        q += f" FROM {table_name} WHERE {from_col} >= :window_start ORDER BY station_id, "
        q += ("product_code, " if product_col else "") + "from_ts"

        rows = db.execute(text(q), {"window_start": window_start}).mappings().all()
        periods: list[PricePeriod] = []
        grouped: dict[tuple[str, str], list] = defaultdict(list)
        for row in rows:
            grouped[(str(row["station_id"]), str(row.get("product_code") or ""))].append(row)
        for (station_id, product_code), items in grouped.items():
            for idx, row in enumerate(items):
                start_ts = _to_datetime(row["from_ts"])
                raw_end = row.get("to_ts") or (items[idx + 1]["from_ts"] if idx + 1 < len(items) else datetime.now(tz=timezone.utc))
                end_ts = _to_datetime(raw_end)
                periods.append(
                    PricePeriod(
                        station_id=station_id,
                        product_code=product_code if (has_product_dim and source_has_product) else "",
                        price=float(row["price"]),
                        start_ts=start_ts,
                        end_ts=end_ts,
                    )
                )
        if periods:
            return periods

    product_expr = Operation.product_code if has_product_dim else literal("")
    rows = (
        db.query(
            Operation.fuel_station_id.label("station_id"),
            product_expr.label("product_code"),
            Operation.unit_price.label("price"),
            Operation.created_at.label("from_ts"),
        )
        .filter(
            Operation.created_at >= window_start,
            Operation.fuel_station_id.isnot(None),
            Operation.status.in_([OperationStatus.CAPTURED, OperationStatus.COMPLETED]),
            Operation.unit_price.isnot(None),
        )
        .order_by(Operation.fuel_station_id, product_expr, Operation.created_at)
        .all()
    )

    grouped_prices: dict[tuple[str, str], list] = defaultdict(list)
    for row in rows:
        grouped_prices[(str(row.station_id), str(row.product_code or ""))].append(row)

    periods: list[PricePeriod] = []
    for (station_id, product_code), items in grouped_prices.items():
        for idx, row in enumerate(items):
            next_ts = items[idx + 1].from_ts if idx + 1 < len(items) else (row.from_ts + timedelta(days=1))
            periods.append(
                PricePeriod(
                    station_id=station_id,
                    product_code=product_code if has_product_dim else "",
                    price=float(row.price),
                    start_ts=row.from_ts,
                    end_ts=next_ts,
                )
            )
    return periods


def _op_volume(op: Operation) -> float:
    if op.quantity is not None and float(op.quantity) > 0:
        return float(op.quantity)
    return 1.0


def compute_period_elasticity(prev_price: float, cur_price: float, prev_q: float, cur_q: float) -> float | None:
    if prev_price <= 0:
        return None
    dp = ((cur_price - prev_price) / prev_price) * 100.0
    if abs(dp) < MIN_PRICE_CHANGE_PCT:
        return None
    dq = 0.0 if prev_q <= 0 else ((cur_q - prev_q) / prev_q) * 100.0
    return dq / dp


def _calculate_elasticity(periods: list[PricePeriod], operations: list[Operation], has_product_dim: bool) -> list[dict]:
    op_groups: dict[tuple[str, str], list[Operation]] = defaultdict(list)
    for op in operations:
        key = (str(op.fuel_station_id), str(op.product_code or "") if has_product_dim else "")
        op_groups[key].append(op)

    by_key: dict[tuple[str, str], list[PricePeriod]] = defaultdict(list)
    for period in periods:
        by_key[(period.station_id, period.product_code if has_product_dim else "")].append(period)

    updated = datetime.now(tz=timezone.utc)
    output: list[dict] = []
    for (station_id, product_code), station_periods in by_key.items():
        sorted_periods = sorted(station_periods, key=lambda p: p.start_ts)
        demand_series: list[tuple[PricePeriod, float, int]] = []
        for period in sorted_periods:
            vol = 0.0
            tx = 0
            for op in op_groups.get((station_id, product_code if has_product_dim else ""), []):
                op_ts = _to_datetime(op.created_at)
                if op_ts >= period.start_ts and op_ts < period.end_ts:
                    vol += _op_volume(op)
                    tx += 1
            demand_series.append((period, vol, tx))

        eis: list[float] = []
        total_volume = sum(v for _, v, _ in demand_series)
        max_dp = 0.0
        low_volume = False
        for idx in range(1, len(demand_series)):
            prev_period, q_prev, tx_prev = demand_series[idx - 1]
            cur_period, q_cur, _ = demand_series[idx]
            if q_prev < MIN_VOLUME_THRESHOLD and tx_prev < MIN_TX_THRESHOLD:
                low_volume = True
                continue
            if prev_period.price <= 0:
                continue
            dp = ((cur_period.price - prev_period.price) / prev_period.price) * 100.0
            max_dp = max(max_dp, abs(dp))
            elasticity = compute_period_elasticity(prev_period.price, cur_period.price, q_prev, q_cur)
            if elasticity is None:
                continue
            eis.append(elasticity)

        note = "OK"
        if not has_product_dim:
            note = "PRODUCT_DIM_MISSING"
        if low_volume and total_volume < MIN_VOLUME_THRESHOLD:
            note = "INSUFFICIENT_VOLUME"
        if not eis:
            note = "INSUFFICIENT_VARIATION" if max_dp < MIN_PRICE_CHANGE_PCT else note

        sample_points = len(eis)
        base_conf = min(1.0, sample_points / 5.0)
        if total_volume < MIN_VOLUME_THRESHOLD:
            base_conf *= 0.6
        if max_dp < 1.0:
            base_conf *= 0.7

        elasticity_score = float(median(eis)) if eis else 0.0
        elasticity_abs = float(median([abs(x) for x in eis])) if eis else 0.0
        output.append(
            {
                "station_id": station_id,
                "product_code": product_code if has_product_dim else "",
                "elasticity_score": elasticity_score,
                "elasticity_abs": elasticity_abs,
                "confidence_score": min(1.0, max(0.0, base_conf)),
                "sample_points": sample_points,
                "total_volume": total_volume,
                "notes": note,
                "updated_at": updated,
            }
        )
    return output


def elasticity_compute(db: Session, window_days: int = 90) -> dict[str, object]:
    window_start = datetime.now(tz=timezone.utc) - timedelta(days=window_days)
    has_product_dim = detect_product_dimension()
    _ensure_ch_table()

    operations = (
        db.query(Operation)
        .filter(
            Operation.created_at >= window_start,
            Operation.fuel_station_id.isnot(None),
            Operation.status.in_([OperationStatus.CAPTURED, OperationStatus.COMPLETED]),
        )
        .all()
    )
    periods = _load_price_periods(db, window_start=window_start, has_product_dim=has_product_dim)
    rows = _calculate_elasticity(periods, operations, has_product_dim)

    db.query(StationElasticity).filter(StationElasticity.window_days == window_days).delete()
    for row in rows:
        db.add(StationElasticity(window_days=window_days, **row))
    db.commit()

    if _ch_enabled() and _ch_ping() and rows:
        payload = "\n".join(
            json.dumps(
                {
                    **row,
                    "station_id": int(float(row["station_id"])),
                    "window_days": window_days,
                    "updated_at": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S"),
                },
                separators=(",", ":"),
            )
            for row in rows
        ) + "\n"
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
    items.sort(key=lambda x: x.get(metric, 0), reverse=True)
    return items[:limit] if not station_id else items
