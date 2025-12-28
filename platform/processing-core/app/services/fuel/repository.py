from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fleet import FleetDriver, FleetVehicle
from app.models.fuel import (
    FuelCard,
    FuelCardGroup,
    FuelLimit,
    FuelNetwork,
    FuelRiskProfile,
    FuelRiskShadowEvent,
    FuelAnomalyEvent,
    FuelAnalyticsEvent,
    FuelMisuseSignal,
    FuelStationNetwork,
    FuelStationOutlier,
    FuelStation,
    FuelTransaction,
    FuelTransactionStatus,
)
from app.models.risk_decision import RiskDecision


def get_card_by_token(db: Session, *, tenant_id: int | None, card_token: str) -> FuelCard | None:
    query = db.query(FuelCard).filter(FuelCard.card_token == card_token)
    if tenant_id is not None:
        query = query.filter(FuelCard.tenant_id == tenant_id)
    return query.one_or_none()


def get_network_by_code(db: Session, *, network_code: str) -> FuelNetwork | None:
    return db.query(FuelNetwork).filter(FuelNetwork.provider_code == network_code).one_or_none()


def get_station_by_code(
    db: Session,
    *,
    network_id: str,
    station_code: str,
) -> FuelStation | None:
    return (
        db.query(FuelStation)
        .filter(FuelStation.network_id == network_id)
        .filter(FuelStation.station_code == station_code)
        .one_or_none()
    )


def get_station_network_by_id(db: Session, *, station_network_id: str) -> FuelStationNetwork | None:
    return db.query(FuelStationNetwork).filter(FuelStationNetwork.id == station_network_id).one_or_none()


def get_vehicle_by_plate(db: Session, *, client_id: str, plate_number: str) -> FleetVehicle | None:
    return (
        db.query(FleetVehicle)
        .filter(FleetVehicle.client_id == client_id)
        .filter(FleetVehicle.plate_number == plate_number)
        .one_or_none()
    )


def get_vehicle_by_id(db: Session, *, vehicle_id: str) -> FleetVehicle | None:
    return db.query(FleetVehicle).filter(FleetVehicle.id == vehicle_id).one_or_none()


def get_driver_by_id(db: Session, *, driver_id: str) -> FleetDriver | None:
    return db.query(FleetDriver).filter(FleetDriver.id == driver_id).one_or_none()


def get_card_group(db: Session, *, group_id: str) -> FuelCardGroup | None:
    return db.query(FuelCardGroup).filter(FuelCardGroup.id == group_id).one_or_none()


def list_active_limits(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    scope_type,
    scope_id: str | None,
    at: datetime,
    currency: str,
    fuel_type_code: str | None = None,
    station_id: str | None = None,
    station_network_id: str | None = None,
) -> list[FuelLimit]:
    query = (
        db.query(FuelLimit)
        .filter(FuelLimit.tenant_id == tenant_id)
        .filter(FuelLimit.client_id == client_id)
        .filter(FuelLimit.scope_type == scope_type)
        .filter(FuelLimit.active.is_(True))
    )
    if scope_id is None:
        query = query.filter(FuelLimit.scope_id.is_(None))
    else:
        query = query.filter(FuelLimit.scope_id == scope_id)
    if fuel_type_code is not None:
        query = query.filter(FuelLimit.fuel_type_code.in_([None, fuel_type_code]))
    query = query.filter(FuelLimit.station_id.in_([None, station_id]))
    query = query.filter(FuelLimit.station_network_id.in_([None, station_network_id]))
    query = query.filter(func.coalesce(FuelLimit.valid_from, at) <= at)
    query = query.filter(func.coalesce(FuelLimit.valid_to, at) >= at)
    query = query.filter(func.coalesce(FuelLimit.currency, currency) == currency)
    return query.all()


def sum_fuel_usage(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    scope_type,
    scope_id: str | None,
    start_at: datetime,
    end_at: datetime,
    limit_type,
    fuel_type_code: str | None = None,
    station_id: str | None = None,
    station_network_id: str | None = None,
) -> int:
    query = (
        db.query(func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0))
        .filter(FuelTransaction.tenant_id == tenant_id)
        .filter(FuelTransaction.client_id == client_id)
        .filter(
            FuelTransaction.status.in_(
                [
                    FuelTransactionStatus.AUTHORIZED,
                    FuelTransactionStatus.REVIEW_REQUIRED,
                    FuelTransactionStatus.SETTLED,
                ]
            )
        )
        .filter(FuelTransaction.occurred_at >= start_at)
        .filter(FuelTransaction.occurred_at < end_at)
    )
    if scope_type == "CLIENT":
        query = query.filter(FuelTransaction.client_id == client_id)
    elif scope_type == "CARD":
        query = query.filter(FuelTransaction.card_id == scope_id)
    elif scope_type == "VEHICLE":
        query = query.filter(FuelTransaction.vehicle_id == scope_id)
    elif scope_type == "DRIVER":
        query = query.filter(FuelTransaction.driver_id == scope_id)
    elif scope_type == "CARD_GROUP":
        query = query.join(FuelCard, FuelTransaction.card_id == FuelCard.id).filter(
            FuelCard.card_group_id == scope_id
        )
    else:
        return 0

    if fuel_type_code is not None:
        query = query.filter(FuelTransaction.fuel_type == fuel_type_code)
    if station_id is not None:
        query = query.filter(FuelTransaction.station_id == station_id)
    if station_network_id is not None:
        query = query.join(FuelStation, FuelTransaction.station_id == FuelStation.id).filter(
            FuelStation.station_network_id == station_network_id
        )

    if limit_type == "COUNT":
        return int(query.with_entities(func.count(FuelTransaction.id)).scalar() or 0)
    if limit_type == "VOLUME":
        return int(query.with_entities(func.coalesce(func.sum(FuelTransaction.volume_ml), 0)).scalar() or 0)
    return int(query.scalar() or 0)


def get_risk_decision_id(db: Session, *, decision_id: str) -> str | None:
    record = db.query(RiskDecision).filter(RiskDecision.decision_id == decision_id).one_or_none()
    if record is None:
        return None
    return str(record.id)


def get_fuel_transaction(db: Session, *, transaction_id: str) -> FuelTransaction | None:
    return db.query(FuelTransaction).filter(FuelTransaction.id == transaction_id).one_or_none()


def list_fuel_transactions(
    db: Session,
    *,
    client_id: str | None = None,
    card_id: str | None = None,
    status: FuelTransactionStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FuelTransaction]:
    query = db.query(FuelTransaction)
    if client_id:
        query = query.filter(FuelTransaction.client_id == client_id)
    if card_id:
        query = query.filter(FuelTransaction.card_id == card_id)
    if status:
        query = query.filter(FuelTransaction.status == status)
    return query.order_by(FuelTransaction.occurred_at.desc()).offset(offset).limit(limit).all()


def add_fuel_transaction(db: Session, transaction: FuelTransaction) -> FuelTransaction:
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_fuel_risk_profile(db: Session, *, client_id: str) -> FuelRiskProfile | None:
    return (
        db.query(FuelRiskProfile)
        .filter(FuelRiskProfile.client_id == client_id)
        .filter(FuelRiskProfile.enabled.is_(True))
        .one_or_none()
    )


def add_risk_shadow_event(db: Session, event: FuelRiskShadowEvent) -> FuelRiskShadowEvent:
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def add_anomaly_event(db: Session, event: FuelAnomalyEvent) -> FuelAnomalyEvent:
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def add_analytics_event(db: Session, event: FuelAnalyticsEvent) -> FuelAnalyticsEvent:
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def add_misuse_signal(db: Session, signal: FuelMisuseSignal) -> FuelMisuseSignal:
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def add_station_outlier(db: Session, outlier: FuelStationOutlier) -> FuelStationOutlier:
    db.add(outlier)
    db.commit()
    db.refresh(outlier)
    return outlier


def list_recent_card_driver_ids(
    db: Session,
    *,
    card_id: str,
    start_at: datetime,
    end_at: datetime,
) -> list[str]:
    rows = (
        db.query(FuelTransaction.driver_id)
        .filter(FuelTransaction.card_id == card_id)
        .filter(FuelTransaction.driver_id.isnot(None))
        .filter(FuelTransaction.occurred_at >= start_at)
        .filter(FuelTransaction.occurred_at <= end_at)
        .distinct()
        .all()
    )
    return [str(row[0]) for row in rows if row[0]]


def avg_card_volume_30d(db: Session, *, card_id: str, start_at: datetime, end_at: datetime) -> float:
    avg = (
        db.query(func.coalesce(func.avg(FuelTransaction.volume_ml), 0))
        .filter(FuelTransaction.card_id == card_id)
        .filter(
            FuelTransaction.status.in_(
                [
                    FuelTransactionStatus.AUTHORIZED,
                    FuelTransactionStatus.REVIEW_REQUIRED,
                    FuelTransactionStatus.SETTLED,
                ]
            )
        )
        .filter(FuelTransaction.occurred_at >= start_at)
        .filter(FuelTransaction.occurred_at <= end_at)
        .scalar()
    )
    return float(avg or 0)


def station_price_avg(
    db: Session, *, station_id: str, network_id: str, start_at: datetime, end_at: datetime
) -> tuple[float, float]:
    station_avg = (
        db.query(func.coalesce(func.avg(FuelTransaction.unit_price_minor), 0))
        .filter(FuelTransaction.station_id == station_id)
        .filter(FuelTransaction.occurred_at >= start_at)
        .filter(FuelTransaction.occurred_at <= end_at)
        .scalar()
    )
    network_avg = (
        db.query(func.coalesce(func.avg(FuelTransaction.unit_price_minor), 0))
        .filter(FuelTransaction.network_id == network_id)
        .filter(FuelTransaction.occurred_at >= start_at)
        .filter(FuelTransaction.occurred_at <= end_at)
        .scalar()
    )
    return float(station_avg or 0), float(network_avg or 0)


def list_fuel_tx_count(
    db: Session,
    *,
    card_id: str,
    start_at: datetime,
    end_at: datetime,
) -> int:
    return (
        db.query(func.count(FuelTransaction.id))
        .filter(FuelTransaction.card_id == card_id)
        .filter(
            FuelTransaction.status.in_(
                [
                    FuelTransactionStatus.AUTHORIZED,
                    FuelTransactionStatus.REVIEW_REQUIRED,
                    FuelTransactionStatus.SETTLED,
                ]
            )
        )
        .filter(FuelTransaction.occurred_at >= start_at)
        .filter(FuelTransaction.occurred_at <= end_at)
        .scalar()
        or 0
    )
