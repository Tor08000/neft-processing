from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fleet_intelligence import (
    FIDriverDaily,
    FIDriverScore,
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
) -> FIDriverScore | None:
    return (
        db.query(FIDriverScore)
        .filter(FIDriverScore.tenant_id == tenant_id)
        .filter(FIDriverScore.client_id == client_id)
        .filter(FIDriverScore.driver_id == driver_id)
        .filter(FIDriverScore.window_days == window_days)
        .order_by(FIDriverScore.computed_at.desc())
        .first()
    )


def get_latest_vehicle_score(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    vehicle_id: str,
    window_days: int,
) -> FIVehicleEfficiencyScore | None:
    return (
        db.query(FIVehicleEfficiencyScore)
        .filter(FIVehicleEfficiencyScore.tenant_id == tenant_id)
        .filter(FIVehicleEfficiencyScore.client_id == client_id)
        .filter(FIVehicleEfficiencyScore.vehicle_id == vehicle_id)
        .filter(FIVehicleEfficiencyScore.window_days == window_days)
        .order_by(FIVehicleEfficiencyScore.computed_at.desc())
        .first()
    )


def get_latest_station_score(
    db: Session,
    *,
    tenant_id: int,
    station_id: str,
    window_days: int,
) -> FIStationTrustScore | None:
    return (
        db.query(FIStationTrustScore)
        .filter(FIStationTrustScore.tenant_id == tenant_id)
        .filter(FIStationTrustScore.station_id == station_id)
        .filter(FIStationTrustScore.window_days == window_days)
        .order_by(FIStationTrustScore.computed_at.desc())
        .first()
    )


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
) -> list[FIDriverScore]:
    subquery = (
        db.query(
            FIDriverScore.driver_id,
            func.max(FIDriverScore.computed_at).label("latest_ts"),
        )
        .filter(FIDriverScore.client_id == client_id)
        .filter(FIDriverScore.window_days == window_days)
        .group_by(FIDriverScore.driver_id)
        .subquery()
    )
    return (
        db.query(FIDriverScore)
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
) -> list[FIVehicleEfficiencyScore]:
    subquery = (
        db.query(
            FIVehicleEfficiencyScore.vehicle_id,
            func.max(FIVehicleEfficiencyScore.computed_at).label("latest_ts"),
        )
        .filter(FIVehicleEfficiencyScore.client_id == client_id)
        .filter(FIVehicleEfficiencyScore.window_days == window_days)
        .group_by(FIVehicleEfficiencyScore.vehicle_id)
        .subquery()
    )
    return (
        db.query(FIVehicleEfficiencyScore)
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
) -> list[FIStationTrustScore]:
    subquery = (
        db.query(
            FIStationTrustScore.station_id,
            func.max(FIStationTrustScore.computed_at).label("latest_ts"),
        )
        .filter(FIStationTrustScore.tenant_id == tenant_id)
        .filter(FIStationTrustScore.window_days == window_days)
        .group_by(FIStationTrustScore.station_id)
        .subquery()
    )
    return (
        db.query(FIStationTrustScore)
        .join(
            subquery,
            (FIStationTrustScore.station_id == subquery.c.station_id)
            & (FIStationTrustScore.computed_at == subquery.c.latest_ts),
        )
        .order_by(FIStationTrustScore.station_id.asc())
        .all()
    )


def latest_scores_for_ids(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
    window_days: int,
) -> dict[str, object | None]:
    return {
        "driver": get_latest_driver_score(
            db,
            tenant_id=tenant_id,
            client_id=client_id,
            driver_id=driver_id,
            window_days=window_days,
        )
        if driver_id
        else None,
        "vehicle": get_latest_vehicle_score(
            db,
            tenant_id=tenant_id,
            client_id=client_id,
            vehicle_id=vehicle_id,
            window_days=window_days,
        )
        if vehicle_id
        else None,
        "station": get_latest_station_score(
            db,
            tenant_id=tenant_id,
            station_id=station_id,
            window_days=window_days,
        )
        if station_id
        else None,
    }


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
    "list_latest_vehicle_scores_by_client",
    "list_latest_station_scores_by_tenant",
    "latest_scores_for_ids",
]
