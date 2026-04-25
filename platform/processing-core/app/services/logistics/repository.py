from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from sqlalchemy import String, cast, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.logistics import (
    LogisticsETASnapshot,
    LogisticsDeviationEvent,
    LogisticsNavigatorExplain,
    LogisticsNavigatorExplainType,
    LogisticsOrder,
    LogisticsOrderStatus,
    LogisticsRiskSignal,
    LogisticsRoute,
    LogisticsRouteConstraint,
    LogisticsRouteStatus,
    LogisticsRouteSnapshot,
    LogisticsStop,
    LogisticsTrackingEvent,
)

ModelT = TypeVar("ModelT")


def id_equals(column, value: object):
    return cast(column, String) == str(value)


def id_in(column, values: list[str] | tuple[str, ...] | set[str]):
    return cast(column, String).in_([str(value) for value in values])


def ids_match(left_column, right_column):
    return cast(left_column, String) == cast(right_column, String)


def refresh_by_id(db: Session, obj: ModelT, model: type[ModelT], identity: object | None = None) -> ModelT:
    lookup_id = identity
    if lookup_id is None:
        try:
            lookup_id = getattr(obj, "id")
        except SQLAlchemyError:
            lookup_id = None
    try:
        db.refresh(obj)
        return obj
    except SQLAlchemyError:
        db.rollback()
        if lookup_id is None:
            raise
        refreshed = db.query(model).filter(id_equals(model.id, lookup_id)).one_or_none()
        if refreshed is None:
            raise
        return refreshed


def get_order(db: Session, *, order_id: str) -> LogisticsOrder | None:
    return db.query(LogisticsOrder).filter(id_equals(LogisticsOrder.id, order_id)).one_or_none()


def list_orders(
    db: Session,
    *,
    client_id: str | None = None,
    status: LogisticsOrderStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[LogisticsOrder]:
    query = db.query(LogisticsOrder)
    if client_id:
        query = query.filter(LogisticsOrder.client_id == client_id)
    if status:
        query = query.filter(LogisticsOrder.status == status)
    return query.order_by(LogisticsOrder.created_at.desc()).offset(offset).limit(limit).all()


def get_route(db: Session, *, route_id: str) -> LogisticsRoute | None:
    return db.query(LogisticsRoute).filter(id_equals(LogisticsRoute.id, route_id)).one_or_none()


def list_routes_for_order(db: Session, *, order_id: str) -> list[LogisticsRoute]:
    return (
        db.query(LogisticsRoute)
        .filter(id_equals(LogisticsRoute.order_id, order_id))
        .order_by(LogisticsRoute.version.desc())
        .all()
    )


def get_active_route(db: Session, *, order_id: str) -> LogisticsRoute | None:
    return (
        db.query(LogisticsRoute)
        .filter(id_equals(LogisticsRoute.order_id, order_id))
        .filter(LogisticsRoute.status == LogisticsRouteStatus.ACTIVE)
        .order_by(LogisticsRoute.version.desc())
        .one_or_none()
    )


def get_route_constraint(db: Session, *, route_id: str) -> LogisticsRouteConstraint | None:
    return (
        db.query(LogisticsRouteConstraint)
        .filter(id_equals(LogisticsRouteConstraint.route_id, route_id))
        .one_or_none()
    )


def get_route_stops(db: Session, *, route_id: str) -> list[LogisticsStop]:
    return (
        db.query(LogisticsStop)
        .filter(id_equals(LogisticsStop.route_id, route_id))
        .order_by(LogisticsStop.sequence.asc())
        .all()
    )


def get_stop(db: Session, *, stop_id: str) -> LogisticsStop | None:
    return db.query(LogisticsStop).filter(id_equals(LogisticsStop.id, stop_id)).one_or_none()


def list_tracking_events(
    db: Session, *, order_id: str, limit: int = 100
) -> list[LogisticsTrackingEvent]:
    return (
        db.query(LogisticsTrackingEvent)
        .filter(id_equals(LogisticsTrackingEvent.order_id, order_id))
        .order_by(LogisticsTrackingEvent.ts.desc())
        .limit(limit)
        .all()
    )


def get_last_tracking_event(db: Session, *, order_id: str) -> LogisticsTrackingEvent | None:
    return (
        db.query(LogisticsTrackingEvent)
        .filter(id_equals(LogisticsTrackingEvent.order_id, order_id))
        .order_by(LogisticsTrackingEvent.ts.desc())
        .first()
    )


def count_tracking_events(db: Session, *, order_id: str) -> int:
    return (
        db.query(func.count(LogisticsTrackingEvent.id))
        .filter(id_equals(LogisticsTrackingEvent.order_id, order_id))
        .scalar()
        or 0
    )


def get_latest_eta_snapshot(db: Session, *, order_id: str) -> LogisticsETASnapshot | None:
    return (
        db.query(LogisticsETASnapshot)
        .filter(id_equals(LogisticsETASnapshot.order_id, order_id))
        .order_by(LogisticsETASnapshot.computed_at.desc())
        .first()
    )


def list_eta_snapshots(
    db: Session, *, order_id: str, limit: int = 10
) -> list[LogisticsETASnapshot]:
    return (
        db.query(LogisticsETASnapshot)
        .filter(id_equals(LogisticsETASnapshot.order_id, order_id))
        .order_by(LogisticsETASnapshot.computed_at.desc())
        .limit(limit)
        .all()
    )


def get_latest_route_snapshot(db: Session, *, route_id: str) -> LogisticsRouteSnapshot | None:
    return (
        db.query(LogisticsRouteSnapshot)
        .filter(id_equals(LogisticsRouteSnapshot.route_id, route_id))
        .order_by(LogisticsRouteSnapshot.created_at.desc())
        .first()
    )


def list_route_snapshots(db: Session, *, route_id: str, limit: int = 5) -> list[LogisticsRouteSnapshot]:
    return (
        db.query(LogisticsRouteSnapshot)
        .filter(id_equals(LogisticsRouteSnapshot.route_id, route_id))
        .order_by(LogisticsRouteSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )


def list_navigator_explains(
    db: Session,
    *,
    route_snapshot_id: str,
    explain_type: LogisticsNavigatorExplainType | None = None,
    limit: int = 10,
) -> list[LogisticsNavigatorExplain]:
    query = db.query(LogisticsNavigatorExplain).filter(
        id_equals(LogisticsNavigatorExplain.route_snapshot_id, route_snapshot_id)
    )
    if explain_type:
        query = query.filter(LogisticsNavigatorExplain.type == explain_type)
    return query.order_by(LogisticsNavigatorExplain.created_at.desc()).limit(limit).all()


def list_recent_risk_signals(
    db: Session,
    *,
    client_id: str,
    vehicle_id: str | None,
    driver_id: str | None,
    since: datetime,
) -> list[LogisticsRiskSignal]:
    query = db.query(LogisticsRiskSignal).filter(LogisticsRiskSignal.client_id == client_id)
    query = query.filter(LogisticsRiskSignal.ts >= since)
    if vehicle_id:
        query = query.filter(id_equals(LogisticsRiskSignal.vehicle_id, vehicle_id))
    if driver_id:
        query = query.filter(id_equals(LogisticsRiskSignal.driver_id, driver_id))
    return query.order_by(LogisticsRiskSignal.ts.desc()).all()


def list_risk_signals(
    db: Session,
    *,
    order_id: str,
    limit: int = 20,
) -> list[LogisticsRiskSignal]:
    return (
        db.query(LogisticsRiskSignal)
        .filter(id_equals(LogisticsRiskSignal.order_id, order_id))
        .order_by(LogisticsRiskSignal.ts.desc())
        .limit(limit)
        .all()
    )


def list_recent_deviation_events(
    db: Session,
    *,
    order_id: str,
    since: datetime,
) -> list[LogisticsDeviationEvent]:
    return (
        db.query(LogisticsDeviationEvent)
        .filter(id_equals(LogisticsDeviationEvent.order_id, order_id))
        .filter(LogisticsDeviationEvent.ts >= since)
        .order_by(LogisticsDeviationEvent.ts.desc())
        .all()
    )


def update_order_timestamp(db: Session, *, order: LogisticsOrder) -> None:
    order.updated_at = datetime.now(tz=order.updated_at.tzinfo) if order.updated_at else datetime.utcnow()
