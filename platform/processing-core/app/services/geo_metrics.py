from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA
from app.models.fuel import FuelStation, FuelTransaction, FuelTransactionStatus
from app.models.geo_metrics import GeoStationMetricsDaily


@dataclass
class GeoStationDailyAggregate:
    tx_count: int = 0
    captured_count: int = 0
    declined_count: int = 0
    amount_sum: Decimal = Decimal("0")
    liters_sum: Decimal = Decimal("0")
    risk_red_count: int = 0
    risk_yellow_count: int = 0


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


def rebuild_geo_station_metrics_for_day(db: Session, target_day: date) -> int:
    if not _table_exists(db, FuelTransaction.__table__.name) or not _table_exists(db, GeoStationMetricsDaily.__table__.name):
        return 0
    day_start = datetime.combine(target_day, time.min, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    transactions = (
        db.query(FuelTransaction)
        .filter(FuelTransaction.occurred_at >= day_start, FuelTransaction.occurred_at < day_end)
        .all()
    )

    grouped: dict[str, GeoStationDailyAggregate] = defaultdict(GeoStationDailyAggregate)

    for transaction in transactions:
        aggregate = grouped[str(transaction.station_id)]
        aggregate.tx_count += 1

        if transaction.status == FuelTransactionStatus.SETTLED:
            aggregate.captured_count += 1
            aggregate.amount_sum += _to_amount(transaction)
            aggregate.liters_sum += _to_liters(transaction)
        elif transaction.status == FuelTransactionStatus.DECLINED:
            aggregate.declined_count += 1

        tags = _risk_tags(transaction)
        if "STATION_RISK_RED" in tags:
            aggregate.risk_red_count += 1
        if "STATION_RISK_YELLOW" in tags:
            aggregate.risk_yellow_count += 1

    db.query(GeoStationMetricsDaily).filter(GeoStationMetricsDaily.day == target_day).delete()

    for station_id, aggregate in grouped.items():
        db.add(
            GeoStationMetricsDaily(
                day=target_day,
                station_id=station_id,
                tx_count=aggregate.tx_count,
                captured_count=aggregate.captured_count,
                declined_count=aggregate.declined_count,
                amount_sum=aggregate.amount_sum,
                liters_sum=aggregate.liters_sum,
                risk_red_count=aggregate.risk_red_count,
                risk_yellow_count=aggregate.risk_yellow_count,
            )
        )

    db.commit()
    return len(grouped)


def geo_metrics_backfill(db: Session, days: int = 7, today: date | None = None) -> list[date]:
    anchor = today or datetime.now(tz=timezone.utc).date()
    rebuilt: list[date] = []
    for delta in range(days):
        target = anchor - timedelta(days=delta)
        rebuild_geo_station_metrics_for_day(db, target)
        rebuilt.append(target)
    return rebuilt


def fetch_top_station_metrics(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    metric: str,
    limit: int,
    risk_zone: str | None = None,
    health_status: str | None = None,
) -> list[dict]:
    if not _table_exists(db, FuelStation.__table__.name) or not _table_exists(db, GeoStationMetricsDaily.__table__.name):
        return []
    metric_columns = {
        "tx_count": func.sum(GeoStationMetricsDaily.tx_count),
        "amount_sum": func.sum(GeoStationMetricsDaily.amount_sum),
        "declined_count": func.sum(GeoStationMetricsDaily.declined_count),
        "captured_count": func.sum(GeoStationMetricsDaily.captured_count),
        "risk_red_count": func.sum(GeoStationMetricsDaily.risk_red_count),
    }
    sort_column = metric_columns[metric]

    query = (
        db.query(
            GeoStationMetricsDaily.station_id,
            func.sum(GeoStationMetricsDaily.tx_count).label("tx_count"),
            func.sum(GeoStationMetricsDaily.captured_count).label("captured_count"),
            func.sum(GeoStationMetricsDaily.declined_count).label("declined_count"),
            func.sum(GeoStationMetricsDaily.amount_sum).label("amount_sum"),
            func.sum(GeoStationMetricsDaily.liters_sum).label("liters_sum"),
            func.sum(GeoStationMetricsDaily.risk_red_count).label("risk_red_count"),
            func.sum(GeoStationMetricsDaily.risk_yellow_count).label("risk_yellow_count"),
            FuelStation.name.label("station_name"),
            FuelStation.city.label("station_address"),
            FuelStation.lat,
            FuelStation.lon,
        )
        .join(FuelStation, FuelStation.id == GeoStationMetricsDaily.station_id)
        .filter(GeoStationMetricsDaily.day >= date_from, GeoStationMetricsDaily.day <= date_to)
        .group_by(GeoStationMetricsDaily.station_id, FuelStation.name, FuelStation.city, FuelStation.lat, FuelStation.lon)
        .order_by(sort_column.desc())
        .limit(limit)
    )

    if risk_zone:
        query = query.filter(FuelStation.risk_zone == risk_zone)
    if health_status:
        query = query.filter(FuelStation.health_status == health_status)

    rows = query.all()
    return [
        {
            "station_id": row.station_id,
            "station_name": row.station_name,
            "station_address": row.station_address,
            "lat": row.lat,
            "lon": row.lon,
            "tx_count": int(row.tx_count or 0),
            "captured_count": int(row.captured_count or 0),
            "declined_count": int(row.declined_count or 0),
            "amount_sum": float(row.amount_sum or 0),
            "liters_sum": float(row.liters_sum or 0),
            "risk_red_count": int(row.risk_red_count or 0),
            "risk_yellow_count": int(row.risk_yellow_count or 0),
        }
        for row in rows
    ]
