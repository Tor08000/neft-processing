from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fleet_intelligence import (
    FIDriverDaily,
    FIDriverScore,
    FITrendSnapshot,
    FITrendEntityType,
    FITrendLabel,
    FITrendMetric,
    FITrendWindow,
    FIStationDaily,
    FIStationTrustScore,
    FIVehicleDaily,
    FIVehicleEfficiencyScore,
)


def upsert_driver_daily(db: Session, payload: dict) -> FIDriverDaily:
    record = (
        db.query(FIDriverDaily)
        .filter(FIDriverDaily.tenant_id == payload["tenant_id"])
        .filter(FIDriverDaily.driver_id == payload["driver_id"])
        .filter(FIDriverDaily.day == payload["day"])
        .one_or_none()
    )
    if record:
        for key, value in payload.items():
            setattr(record, key, value)
        return record
    record = FIDriverDaily(**payload)
    db.add(record)
    return record


def upsert_vehicle_daily(db: Session, payload: dict) -> FIVehicleDaily:
    record = (
        db.query(FIVehicleDaily)
        .filter(FIVehicleDaily.tenant_id == payload["tenant_id"])
        .filter(FIVehicleDaily.vehicle_id == payload["vehicle_id"])
        .filter(FIVehicleDaily.day == payload["day"])
        .one_or_none()
    )
    if record:
        for key, value in payload.items():
            setattr(record, key, value)
        return record
    record = FIVehicleDaily(**payload)
    db.add(record)
    return record


def upsert_station_daily(db: Session, payload: dict) -> FIStationDaily:
    record = (
        db.query(FIStationDaily)
        .filter(FIStationDaily.tenant_id == payload["tenant_id"])
        .filter(FIStationDaily.station_id == payload["station_id"])
        .filter(FIStationDaily.day == payload["day"])
        .one_or_none()
    )
    if record:
        for key, value in payload.items():
            setattr(record, key, value)
        return record
    record = FIStationDaily(**payload)
    db.add(record)
    return record


def create_driver_score(db: Session, payload: dict) -> FIDriverScore:
    record = FIDriverScore(**payload)
    db.add(record)
    return record


def create_vehicle_score(db: Session, payload: dict) -> FIVehicleEfficiencyScore:
    record = FIVehicleEfficiencyScore(**payload)
    db.add(record)
    return record


def create_station_score(db: Session, payload: dict) -> FIStationTrustScore:
    record = FIStationTrustScore(**payload)
    db.add(record)
    return record


def list_driver_daily_window(
    db: Session, *, tenant_id: int, driver_id: str, start_day: date, end_day: date
) -> list[FIDriverDaily]:
    return (
        db.query(FIDriverDaily)
        .filter(FIDriverDaily.tenant_id == tenant_id)
        .filter(FIDriverDaily.driver_id == driver_id)
        .filter(FIDriverDaily.day >= start_day)
        .filter(FIDriverDaily.day <= end_day)
        .order_by(FIDriverDaily.day.asc())
        .all()
    )


def list_vehicle_daily_window(
    db: Session, *, tenant_id: int, vehicle_id: str, start_day: date, end_day: date
) -> list[FIVehicleDaily]:
    return (
        db.query(FIVehicleDaily)
        .filter(FIVehicleDaily.tenant_id == tenant_id)
        .filter(FIVehicleDaily.vehicle_id == vehicle_id)
        .filter(FIVehicleDaily.day >= start_day)
        .filter(FIVehicleDaily.day <= end_day)
        .order_by(FIVehicleDaily.day.asc())
        .all()
    )


def list_station_daily_window(
    db: Session, *, tenant_id: int, station_id: str, start_day: date, end_day: date
) -> list[FIStationDaily]:
    return (
        db.query(FIStationDaily)
        .filter(FIStationDaily.tenant_id == tenant_id)
        .filter(FIStationDaily.station_id == station_id)
        .filter(FIStationDaily.day >= start_day)
        .filter(FIStationDaily.day <= end_day)
        .order_by(FIStationDaily.day.asc())
        .all()
    )


def list_station_network_avg_volume(
    db: Session,
    *,
    tenant_id: int,
    network_id: str | None,
    start_day: date,
    end_day: date,
) -> float | None:
    if not network_id:
        return None
    result = (
        db.query(func.avg(FIStationDaily.avg_volume_ml))
        .filter(FIStationDaily.tenant_id == tenant_id)
        .filter(FIStationDaily.network_id == network_id)
        .filter(FIStationDaily.day >= start_day)
        .filter(FIStationDaily.day <= end_day)
        .one()
    )
    return float(result[0]) if result and result[0] is not None else None


def get_latest_driver_score(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    driver_id: str,
    window_days: int,
    as_of: datetime | None = None,
) -> FIDriverScore | None:
    query = (
        db.query(FIDriverScore)
        .filter(FIDriverScore.tenant_id == tenant_id)
        .filter(FIDriverScore.client_id == client_id)
        .filter(FIDriverScore.driver_id == driver_id)
        .filter(FIDriverScore.window_days == window_days)
    )
    if as_of is not None:
        query = query.filter(FIDriverScore.computed_at <= as_of)
    return query.order_by(FIDriverScore.computed_at.desc()).first()


def get_latest_vehicle_score(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    vehicle_id: str,
    window_days: int,
    as_of: datetime | None = None,
) -> FIVehicleEfficiencyScore | None:
    query = (
        db.query(FIVehicleEfficiencyScore)
        .filter(FIVehicleEfficiencyScore.tenant_id == tenant_id)
        .filter(FIVehicleEfficiencyScore.client_id == client_id)
        .filter(FIVehicleEfficiencyScore.vehicle_id == vehicle_id)
        .filter(FIVehicleEfficiencyScore.window_days == window_days)
    )
    if as_of is not None:
        query = query.filter(FIVehicleEfficiencyScore.computed_at <= as_of)
    return query.order_by(FIVehicleEfficiencyScore.computed_at.desc()).first()


def get_latest_station_score(
    db: Session,
    *,
    tenant_id: int,
    station_id: str,
    window_days: int,
    as_of: datetime | None = None,
) -> FIStationTrustScore | None:
    query = (
        db.query(FIStationTrustScore)
        .filter(FIStationTrustScore.tenant_id == tenant_id)
        .filter(FIStationTrustScore.station_id == station_id)
        .filter(FIStationTrustScore.window_days == window_days)
    )
    if as_of is not None:
        query = query.filter(FIStationTrustScore.computed_at <= as_of)
    return query.order_by(FIStationTrustScore.computed_at.desc()).first()


def list_driver_scores(
    db: Session,
    *,
    client_id: str,
    window_days: int,
) -> list[FIDriverScore]:
    return (
        db.query(FIDriverScore)
        .filter(FIDriverScore.client_id == client_id)
        .filter(FIDriverScore.window_days == window_days)
        .order_by(FIDriverScore.computed_at.desc())
        .all()
    )


def list_vehicle_scores(
    db: Session,
    *,
    client_id: str,
    window_days: int,
) -> list[FIVehicleEfficiencyScore]:
    return (
        db.query(FIVehicleEfficiencyScore)
        .filter(FIVehicleEfficiencyScore.client_id == client_id)
        .filter(FIVehicleEfficiencyScore.window_days == window_days)
        .order_by(FIVehicleEfficiencyScore.computed_at.desc())
        .all()
    )


def list_station_scores(
    db: Session,
    *,
    tenant_id: int,
    window_days: int,
) -> list[FIStationTrustScore]:
    return (
        db.query(FIStationTrustScore)
        .filter(FIStationTrustScore.tenant_id == tenant_id)
        .filter(FIStationTrustScore.window_days == window_days)
        .order_by(FIStationTrustScore.computed_at.desc())
        .all()
    )


def list_latest_driver_scores_by_client(
    db: Session,
    *,
    client_id: str,
    window_days: int,
    as_of: datetime | None = None,
) -> list[FIDriverScore]:
    subquery_query = db.query(
        FIDriverScore.driver_id,
        func.max(FIDriverScore.computed_at).label("latest_ts"),
    ).filter(FIDriverScore.client_id == client_id).filter(FIDriverScore.window_days == window_days)
    if as_of is not None:
        subquery_query = subquery_query.filter(FIDriverScore.computed_at <= as_of)
    subquery = subquery_query.group_by(FIDriverScore.driver_id).subquery()
    return (
        db.query(FIDriverScore)
        .filter(FIDriverScore.window_days == window_days)
        .join(
            subquery,
            (FIDriverScore.driver_id == subquery.c.driver_id)
            & (FIDriverScore.computed_at == subquery.c.latest_ts),
        )
        .order_by(FIDriverScore.driver_id.asc())
        .all()
    )


def list_latest_driver_scores_by_tenant(
    db: Session,
    *,
    tenant_id: int,
    window_days: int,
    as_of: datetime | None = None,
) -> list[FIDriverScore]:
    subquery_query = db.query(
        FIDriverScore.driver_id,
        func.max(FIDriverScore.computed_at).label("latest_ts"),
    ).filter(FIDriverScore.tenant_id == tenant_id).filter(FIDriverScore.window_days == window_days)
    if as_of is not None:
        subquery_query = subquery_query.filter(FIDriverScore.computed_at <= as_of)
    subquery = subquery_query.group_by(FIDriverScore.driver_id).subquery()
    return (
        db.query(FIDriverScore)
        .filter(FIDriverScore.window_days == window_days)
        .join(
            subquery,
            (FIDriverScore.driver_id == subquery.c.driver_id)
            & (FIDriverScore.computed_at == subquery.c.latest_ts),
        )
        .order_by(FIDriverScore.driver_id.asc())
        .all()
    )


def list_latest_vehicle_scores_by_client(
    db: Session,
    *,
    client_id: str,
    window_days: int,
    as_of: datetime | None = None,
) -> list[FIVehicleEfficiencyScore]:
    subquery_query = db.query(
        FIVehicleEfficiencyScore.vehicle_id,
        func.max(FIVehicleEfficiencyScore.computed_at).label("latest_ts"),
    ).filter(FIVehicleEfficiencyScore.client_id == client_id).filter(
        FIVehicleEfficiencyScore.window_days == window_days
    )
    if as_of is not None:
        subquery_query = subquery_query.filter(FIVehicleEfficiencyScore.computed_at <= as_of)
    subquery = subquery_query.group_by(FIVehicleEfficiencyScore.vehicle_id).subquery()
    return (
        db.query(FIVehicleEfficiencyScore)
        .filter(FIVehicleEfficiencyScore.window_days == window_days)
        .join(
            subquery,
            (FIVehicleEfficiencyScore.vehicle_id == subquery.c.vehicle_id)
            & (FIVehicleEfficiencyScore.computed_at == subquery.c.latest_ts),
        )
        .order_by(FIVehicleEfficiencyScore.vehicle_id.asc())
        .all()
    )


def list_latest_vehicle_scores_by_tenant(
    db: Session,
    *,
    tenant_id: int,
    window_days: int,
    as_of: datetime | None = None,
) -> list[FIVehicleEfficiencyScore]:
    subquery_query = db.query(
        FIVehicleEfficiencyScore.vehicle_id,
        func.max(FIVehicleEfficiencyScore.computed_at).label("latest_ts"),
    ).filter(FIVehicleEfficiencyScore.tenant_id == tenant_id).filter(
        FIVehicleEfficiencyScore.window_days == window_days
    )
    if as_of is not None:
        subquery_query = subquery_query.filter(FIVehicleEfficiencyScore.computed_at <= as_of)
    subquery = subquery_query.group_by(FIVehicleEfficiencyScore.vehicle_id).subquery()
    return (
        db.query(FIVehicleEfficiencyScore)
        .filter(FIVehicleEfficiencyScore.window_days == window_days)
        .join(
            subquery,
            (FIVehicleEfficiencyScore.vehicle_id == subquery.c.vehicle_id)
            & (FIVehicleEfficiencyScore.computed_at == subquery.c.latest_ts),
        )
        .order_by(FIVehicleEfficiencyScore.vehicle_id.asc())
        .all()
    )


def list_latest_station_scores_by_tenant(
    db: Session,
    *,
    tenant_id: int,
    window_days: int,
    as_of: datetime | None = None,
) -> list[FIStationTrustScore]:
    subquery_query = db.query(
        FIStationTrustScore.station_id,
        func.max(FIStationTrustScore.computed_at).label("latest_ts"),
    ).filter(FIStationTrustScore.tenant_id == tenant_id).filter(FIStationTrustScore.window_days == window_days)
    if as_of is not None:
        subquery_query = subquery_query.filter(FIStationTrustScore.computed_at <= as_of)
    subquery = subquery_query.group_by(FIStationTrustScore.station_id).subquery()
    return (
        db.query(FIStationTrustScore)
        .filter(FIStationTrustScore.window_days == window_days)
        .join(
            subquery,
            (FIStationTrustScore.station_id == subquery.c.station_id)
            & (FIStationTrustScore.computed_at == subquery.c.latest_ts),
        )
        .order_by(FIStationTrustScore.station_id.asc())
        .all()
    )


def list_latest_station_scores_by_tenant_network(
    db: Session,
    *,
    tenant_id: int,
    window_days: int,
    network_id: str | None,
    as_of: datetime | None = None,
) -> list[FIStationTrustScore]:
    subquery_query = db.query(
        FIStationTrustScore.station_id,
        func.max(FIStationTrustScore.computed_at).label("latest_ts"),
    ).filter(FIStationTrustScore.tenant_id == tenant_id).filter(FIStationTrustScore.window_days == window_days)
    if network_id is not None:
        subquery_query = subquery_query.filter(FIStationTrustScore.network_id == network_id)
    if as_of is not None:
        subquery_query = subquery_query.filter(FIStationTrustScore.computed_at <= as_of)
    subquery = subquery_query.group_by(FIStationTrustScore.station_id).subquery()
    query = (
        db.query(FIStationTrustScore)
        .filter(FIStationTrustScore.window_days == window_days)
        .join(
            subquery,
            (FIStationTrustScore.station_id == subquery.c.station_id)
            & (FIStationTrustScore.computed_at == subquery.c.latest_ts),
        )
        .order_by(FIStationTrustScore.station_id.asc())
    )
    if network_id is not None:
        query = query.filter(FIStationTrustScore.network_id == network_id)
    return query.all()


def list_station_risk_block_rates(
    db: Session,
    *,
    tenant_id: int,
    start_day: date,
    end_day: date,
    network_id: str | None = None,
) -> dict[str, float]:
    query = (
        db.query(
            FIStationDaily.station_id,
            func.sum(FIStationDaily.risk_block_count).label("risk_block_count"),
            func.sum(FIStationDaily.tx_count).label("tx_count"),
        )
        .filter(FIStationDaily.tenant_id == tenant_id)
        .filter(FIStationDaily.day >= start_day)
        .filter(FIStationDaily.day <= end_day)
    )
    if network_id is not None:
        query = query.filter(FIStationDaily.network_id == network_id)
    query = query.group_by(FIStationDaily.station_id)
    rates: dict[str, float] = {}
    for station_id, risk_block_count, tx_count in query.all():
        if tx_count:
            rates[str(station_id)] = float(risk_block_count or 0) / float(tx_count)
    return rates


def latest_scores_for_ids(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
    window_days: int,
    as_of: datetime | None = None,
) -> dict[str, object | None]:
    return {
        "driver": get_latest_driver_score(
            db,
            tenant_id=tenant_id,
            client_id=client_id,
            driver_id=driver_id,
            window_days=window_days,
            as_of=as_of,
        )
        if driver_id
        else None,
        "vehicle": get_latest_vehicle_score(
            db,
            tenant_id=tenant_id,
            client_id=client_id,
            vehicle_id=vehicle_id,
            window_days=window_days,
            as_of=as_of,
        )
        if vehicle_id
        else None,
        "station": get_latest_station_score(
            db,
            tenant_id=tenant_id,
            station_id=station_id,
            window_days=window_days,
            as_of=as_of,
        )
        if station_id
        else None,
    }


def list_vehicle_scores_window(
    db: Session,
    *,
    client_id: str,
    vehicle_id: str,
    window_days: int,
    start_at: datetime,
    end_at: datetime,
) -> list[FIVehicleEfficiencyScore]:
    return (
        db.query(FIVehicleEfficiencyScore)
        .filter(FIVehicleEfficiencyScore.client_id == client_id)
        .filter(FIVehicleEfficiencyScore.vehicle_id == vehicle_id)
        .filter(FIVehicleEfficiencyScore.window_days == window_days)
        .filter(FIVehicleEfficiencyScore.computed_at >= start_at)
        .filter(FIVehicleEfficiencyScore.computed_at <= end_at)
        .order_by(FIVehicleEfficiencyScore.computed_at.desc())
        .all()
    )


def upsert_trend_snapshot(db: Session, payload: dict) -> FITrendSnapshot:
    record = (
        db.query(FITrendSnapshot)
        .filter(FITrendSnapshot.tenant_id == payload["tenant_id"])
        .filter(FITrendSnapshot.entity_type == payload["entity_type"])
        .filter(FITrendSnapshot.entity_id == payload["entity_id"])
        .filter(FITrendSnapshot.metric == payload["metric"])
        .filter(FITrendSnapshot.window == payload["window"])
        .filter(FITrendSnapshot.computed_day == payload["computed_day"])
        .one_or_none()
    )
    if record:
        for key, value in payload.items():
            setattr(record, key, value)
        return record
    record = FITrendSnapshot(**payload)
    db.add(record)
    return record


def list_trend_snapshots(
    db: Session,
    *,
    entity_type: FITrendEntityType,
    metric: FITrendMetric,
    client_id: str | None = None,
    tenant_id: int | None = None,
    day: date | None = None,
    label: FITrendLabel | None = None,
) -> list[FITrendSnapshot]:
    query = (
        db.query(FITrendSnapshot)
        .filter(FITrendSnapshot.entity_type == entity_type)
        .filter(FITrendSnapshot.metric == metric)
    )
    if client_id is not None:
        query = query.filter(FITrendSnapshot.client_id == client_id)
    if tenant_id is not None:
        query = query.filter(FITrendSnapshot.tenant_id == tenant_id)
    if day is not None:
        query = query.filter(FITrendSnapshot.computed_day == day)
    if label is not None:
        query = query.filter(FITrendSnapshot.label == label)
    return query.order_by(FITrendSnapshot.computed_at.desc()).all()


def get_latest_trend_snapshot(
    db: Session,
    *,
    tenant_id: int,
    entity_type: FITrendEntityType,
    entity_id: str,
    metric: FITrendMetric,
    window: FITrendWindow,
) -> FITrendSnapshot | None:
    return (
        db.query(FITrendSnapshot)
        .filter(FITrendSnapshot.tenant_id == tenant_id)
        .filter(FITrendSnapshot.entity_type == entity_type)
        .filter(FITrendSnapshot.entity_id == entity_id)
        .filter(FITrendSnapshot.metric == metric)
        .filter(FITrendSnapshot.window == window)
        .order_by(FITrendSnapshot.computed_at.desc())
        .first()
    )


__all__ = [
    "upsert_driver_daily",
    "upsert_vehicle_daily",
    "upsert_station_daily",
    "create_driver_score",
    "create_vehicle_score",
    "create_station_score",
    "list_driver_daily_window",
    "list_vehicle_daily_window",
    "list_station_daily_window",
    "list_station_network_avg_volume",
    "get_latest_driver_score",
    "get_latest_vehicle_score",
    "get_latest_station_score",
    "list_driver_scores",
    "list_vehicle_scores",
    "list_station_scores",
    "list_latest_driver_scores_by_client",
    "list_latest_driver_scores_by_tenant",
    "list_latest_vehicle_scores_by_client",
    "list_latest_vehicle_scores_by_tenant",
    "list_latest_station_scores_by_tenant",
    "list_latest_station_scores_by_tenant_network",
    "latest_scores_for_ids",
    "list_vehicle_scores_window",
    "upsert_trend_snapshot",
    "list_trend_snapshots",
    "get_latest_trend_snapshot",
    "list_station_risk_block_rates",
]
