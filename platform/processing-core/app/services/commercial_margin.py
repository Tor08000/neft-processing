from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import requests
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings
from sqlalchemy import and_, func, inspect, text
from sqlalchemy.orm import Session

from app.models.clearing_batch_operation import ClearingBatchOperation
from app.models.fuel import FuelStation
from app.models.operation import Operation, OperationStatus
from app.models.station_margin import StationMarginDay

logger = get_logger(__name__)
settings = get_settings()

MODEL_KEYWORDS = ("Settlement", "Clearing", "Payout", "Ledger", "Reconciliation", "Batch", "Item")
TABLE_PATTERNS = ["%settle%", "%clearing%", "%payout%", "%ledger%", "%recon%", "%batch%", "%item%"]


@dataclass(frozen=True)
class MarginMapping:
    settlement_table: str
    revenue_table: str
    join_key: str
    station_key: str
    day_semantics: str
    cost_expr: str
    revenue_expr: str


def _model_candidates() -> list[str]:
    root = Path(__file__).resolve().parents[1] / "models"
    found: list[str] = []
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and any(k in node.name for k in MODEL_KEYWORDS):
                found.append(f"{path.name}:{node.name}")
    return sorted(found)


def _table_candidates(db: Session) -> list[str]:
    if db.bind.dialect.name == "postgresql":
        rows = db.execute(
            text(
                """
                SELECT tablename FROM pg_catalog.pg_tables
                WHERE schemaname = :schema
                AND (
                    tablename ILIKE :p1 OR tablename ILIKE :p2 OR tablename ILIKE :p3 OR
                    tablename ILIKE :p4 OR tablename ILIKE :p5 OR tablename ILIKE :p6 OR tablename ILIKE :p7
                )
                ORDER BY tablename
                """
            ),
            {"schema": "processing_core", "p1": TABLE_PATTERNS[0], "p2": TABLE_PATTERNS[1], "p3": TABLE_PATTERNS[2], "p4": TABLE_PATTERNS[3], "p5": TABLE_PATTERNS[4], "p6": TABLE_PATTERNS[5], "p7": TABLE_PATTERNS[6]},
        ).fetchall()
        return [str(r[0]) for r in rows]
    return sorted(t for t in inspect(db.bind).get_table_names() if any(p.strip("%") in t for p in TABLE_PATTERNS))


def discover_margin_mapping(db: Session) -> tuple[MarginMapping, dict[str, object]]:
    mapping = MarginMapping(
        settlement_table="clearing_batch_operation",
        revenue_table="operations",
        join_key="operation_id",
        station_key="operations.fuel_station_id",
        day_semantics="UTC day from operations.created_at",
        cost_expr="clearing_batch_operation.amount / 100.0",
        revenue_expr="COALESCE(NULLIF(operations.captured_amount, 0), operations.amount) / 100.0",
    )
    report = {
        "candidate_tables": _table_candidates(db),
        "candidate_models": _model_candidates(),
        "chosen": mapping.__dict__,
    }
    return mapping, report


def _ch_enabled() -> bool:
    return settings.GEO_ANALYTICS_BACKEND.lower() == "clickhouse"


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


def _ch_query(query: str) -> list[dict]:
    response = requests.post(
        f"{settings.CLICKHOUSE_URL.rstrip('/')}/",
        params={"database": settings.CLICKHOUSE_DB, "query": f"{query} FORMAT JSONEachRow"},
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def _ch_insert(rows: list[dict]) -> None:
    if not rows:
        return
    payload = "\n".join(json.dumps(item, separators=(",", ":")) for item in rows) + "\n"
    response = requests.post(
        f"{settings.CLICKHOUSE_URL.rstrip('/')}/",
        params={"database": settings.CLICKHOUSE_DB, "query": "INSERT INTO neft_geo.fact_station_margin_day FORMAT JSONEachRow"},
        data=payload.encode("utf-8"),
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)


def _compute_rows(db: Session, target_day: date) -> list[dict]:
    start = datetime.combine(target_day, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    revenue_expr = (func.coalesce(func.nullif(Operation.captured_amount, 0), Operation.amount) / 100.0)
    cost_expr = (func.coalesce(ClearingBatchOperation.amount, 0) / 100.0)
    rows = (
        db.query(
            Operation.fuel_station_id.label("station_id"),
            func.sum(revenue_expr).label("revenue_sum"),
            func.sum(cost_expr).label("cost_sum"),
            func.count(Operation.id).label("tx_count"),
        )
        .outerjoin(ClearingBatchOperation, ClearingBatchOperation.operation_id == Operation.operation_id)
        .filter(
            Operation.created_at >= start,
            Operation.created_at < end,
            Operation.fuel_station_id.isnot(None),
            Operation.status.in_([OperationStatus.CAPTURED, OperationStatus.COMPLETED]),
        )
        .group_by(Operation.fuel_station_id)
        .all()
    )
    output: list[dict] = []
    for row in rows:
        revenue = float(row.revenue_sum or 0)
        cost = float(row.cost_sum or 0)
        output.append(
            {
                "day": target_day,
                "station_id": str(row.station_id),
                "revenue_sum": revenue,
                "cost_sum": cost,
                "gross_margin": revenue - cost,
                "tx_count": int(row.tx_count or 0),
                "updated_at": datetime.now(tz=timezone.utc),
            }
        )
    return output


def rebuild_station_margin_for_day(db: Session, target_day: date) -> int:
    rows = _compute_rows(db, target_day)
    db.query(StationMarginDay).filter(StationMarginDay.day == target_day).delete()
    for row in rows:
        db.add(StationMarginDay(**row))
    db.commit()

    if _ch_enabled() and _ch_ping():
        try:
            _ch_exec(
                """
                CREATE TABLE IF NOT EXISTS neft_geo.fact_station_margin_day (
                    day Date,
                    station_id String,
                    revenue_sum Float64,
                    cost_sum Float64,
                    gross_margin Float64,
                    tx_count UInt32,
                    updated_at DateTime
                ) ENGINE = SummingMergeTree
                PARTITION BY toYYYYMM(day)
                ORDER BY (day, station_id)
                """
            )
            _ch_exec("SET mutations_sync = 1")
            _ch_exec(f"ALTER TABLE neft_geo.fact_station_margin_day DELETE WHERE day = toDate('{target_day.isoformat()}')")
            _ch_insert(
                [
                    {
                        "day": row["day"].isoformat(),
                        "station_id": row["station_id"],
                        "revenue_sum": row["revenue_sum"],
                        "cost_sum": row["cost_sum"],
                        "gross_margin": row["gross_margin"],
                        "tx_count": row["tx_count"],
                        "updated_at": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for row in rows
                ]
            )
        except Exception:
            logger.exception("commercial.margin_clickhouse_write_failed")

    logger.info(
        "commercial.margin_day_rebuilt day=%s stations=%s total_revenue=%s total_cost=%s total_margin=%s",
        target_day.isoformat(),
        len(rows),
        round(sum(r["revenue_sum"] for r in rows), 2),
        round(sum(r["cost_sum"] for r in rows), 2),
        round(sum(r["gross_margin"] for r in rows), 2),
    )
    return len(rows)


def margin_build_daily(db: Session, days_back: int = 7, today: date | None = None) -> list[date]:
    anchor = today or datetime.now(tz=timezone.utc).date()
    rebuilt: list[date] = []
    for delta in range(days_back):
        day = anchor - timedelta(days=delta)
        rebuild_station_margin_for_day(db, day)
        rebuilt.append(day)
    return rebuilt


def fetch_station_margin(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    sort_by: str,
    order: str,
    limit: int,
    partner_id: str | None,
    risk_zone: str | None,
    health_status: str | None,
) -> list[dict]:
    reverse = order == "desc"
    if _ch_enabled() and _ch_ping():
        try:
            rows = _ch_query(
                f"""
                SELECT station_id, sum(revenue_sum) AS revenue_sum, sum(cost_sum) AS cost_sum,
                       sum(gross_margin) AS gross_margin, toUInt32(sum(tx_count)) AS tx_count
                FROM neft_geo.fact_station_margin_day
                WHERE day >= toDate('{date_from.isoformat()}') AND day <= toDate('{date_to.isoformat()}')
                GROUP BY station_id
                """
            )
            by_station = {str(r["station_id"]): r for r in rows}
            q = db.query(FuelStation).filter(FuelStation.id.in_(list(by_station.keys())))
            if partner_id:
                q = q.filter(FuelStation.network_id == partner_id)
            if risk_zone:
                q = q.filter(FuelStation.risk_zone == risk_zone)
            if health_status:
                q = q.filter(FuelStation.health_status == health_status)
            items = []
            for st in q.all():
                agg = by_station.get(str(st.id), {})
                rev = float(agg.get("revenue_sum", 0) or 0)
                cost = float(agg.get("cost_sum", 0) or 0)
                gm = float(agg.get("gross_margin", rev - cost) or 0)
                items.append({
                    "station_id": str(st.id),
                    "station_name": st.name,
                    "station_address": st.city,
                    "lat": st.lat,
                    "lon": st.lon,
                    "revenue_sum": rev,
                    "cost_sum": cost,
                    "gross_margin": gm,
                    "margin_pct": (gm / rev) if rev else 0.0,
                    "tx_count": int(agg.get("tx_count", 0) or 0),
                })
            items.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
            return items[:limit]
        except Exception:
            logger.exception("commercial.margin_clickhouse_read_failed")

    sort_column = {
        "gross_margin": func.sum(StationMarginDay.gross_margin),
        "margin_pct": (func.sum(StationMarginDay.gross_margin) / func.nullif(func.sum(StationMarginDay.revenue_sum), 0)),
        "revenue_sum": func.sum(StationMarginDay.revenue_sum),
        "cost_sum": func.sum(StationMarginDay.cost_sum),
    }[sort_by]
    query = (
        db.query(
            StationMarginDay.station_id,
            FuelStation.name.label("station_name"),
            FuelStation.city.label("station_address"),
            FuelStation.lat,
            FuelStation.lon,
            func.sum(StationMarginDay.revenue_sum).label("revenue_sum"),
            func.sum(StationMarginDay.cost_sum).label("cost_sum"),
            func.sum(StationMarginDay.gross_margin).label("gross_margin"),
            func.sum(StationMarginDay.tx_count).label("tx_count"),
        )
        .join(FuelStation, FuelStation.id == StationMarginDay.station_id)
        .filter(and_(StationMarginDay.day >= date_from, StationMarginDay.day <= date_to))
        .group_by(StationMarginDay.station_id, FuelStation.name, FuelStation.city, FuelStation.lat, FuelStation.lon)
    )
    if partner_id:
        query = query.filter(FuelStation.network_id == partner_id)
    if risk_zone:
        query = query.filter(FuelStation.risk_zone == risk_zone)
    if health_status:
        query = query.filter(FuelStation.health_status == health_status)
    query = query.order_by(sort_column.desc() if reverse else sort_column.asc()).limit(limit)
    rows = query.all()
    return [
        {
            "station_id": str(row.station_id),
            "station_name": row.station_name,
            "station_address": row.station_address,
            "lat": row.lat,
            "lon": row.lon,
            "revenue_sum": float(row.revenue_sum or 0),
            "cost_sum": float(row.cost_sum or 0),
            "gross_margin": float(row.gross_margin or 0),
            "margin_pct": (float(row.gross_margin or 0) / float(row.revenue_sum)) if float(row.revenue_sum or 0) else 0.0,
            "tx_count": int(row.tx_count or 0),
        }
        for row in rows
    ]
