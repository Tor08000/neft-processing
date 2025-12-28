from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.logistics import (
    LogisticsETASnapshot,
    LogisticsDeviationEvent,
    LogisticsOrder,
    LogisticsOrderStatus,
    LogisticsRiskSignal,
    LogisticsRoute,
    LogisticsRouteConstraint,
    LogisticsRouteStatus,
    LogisticsStop,
    LogisticsTrackingEvent,
)


def get_order(db: Session, *, order_id: str) -> LogisticsOrder | None:
    return db.query(LogisticsOrder).filter(LogisticsOrder.id == order_id).one_or_none()


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
    return db.query(LogisticsRoute).filter(LogisticsRoute.id == route_id).one_or_none()


def list_routes_for_order(db: Session, *, order_id: str) -> list[LogisticsRoute]:
    return (
        db.query(LogisticsRoute)
        .filter(LogisticsRoute.order_id == order_id)
        .order_by(LogisticsRoute.version.desc())
        .all()
    )


def get_active_route(db: Session, *, order_id: str) -> LogisticsRoute | None:
    return (
        db.query(LogisticsRoute)
        .filter(LogisticsRoute.order_id == order_id)
        .filter(LogisticsRoute.status == LogisticsRouteStatus.ACTIVE)
        .order_by(LogisticsRoute.version.desc())
        .one_or_none()
    )


def get_route_constraint(db: Session, *, route_id: str) -> LogisticsRouteConstraint | None:
    return (
        db.query(LogisticsRouteConstraint)
        .filter(LogisticsRouteConstraint.route_id == route_id)
        .one_or_none()
    )


def get_route_stops(db: Session, *, route_id: str) -> list[LogisticsStop]:
    return (
        db.query(LogisticsStop)
        .filter(LogisticsStop.route_id == route_id)
        .order_by(LogisticsStop.sequence.asc())
        .all()
    )


def get_stop(db: Session, *, stop_id: str) -> LogisticsStop | None:
    return db.query(LogisticsStop).filter(LogisticsStop.id == stop_id).one_or_none()


def list_tracking_events(
    db: Session, *, order_id: str, limit: int = 100
) -> list[LogisticsTrackingEvent]:
    return (
        db.query(LogisticsTrackingEvent)
        .filter(LogisticsTrackingEvent.order_id == order_id)
        .order_by(LogisticsTrackingEvent.ts.desc())
        .limit(limit)
        .all()
    )


def get_last_tracking_event(db: Session, *, order_id: str) -> LogisticsTrackingEvent | None:
    return (
        db.query(LogisticsTrackingEvent)
        .filter(LogisticsTrackingEvent.order_id == order_id)
        .order_by(LogisticsTrackingEvent.ts.desc())
        .first()
    )


def count_tracking_events(db: Session, *, order_id: str) -> int:
    return (
        db.query(func.count(LogisticsTrackingEvent.id))
        .filter(LogisticsTrackingEvent.order_id == order_id)
        .scalar()
        or 0
    )


def get_latest_eta_snapshot(db: Session, *, order_id: str) -> LogisticsETASnapshot | None:
    return (
        db.query(LogisticsETASnapshot)
        .filter(LogisticsETASnapshot.order_id == order_id)
        .order_by(LogisticsETASnapshot.computed_at.desc())
        .first()
    )


def list_eta_snapshots(
    db: Session, *, order_id: str, limit: int = 10
) -> list[LogisticsETASnapshot]:
    return (
        db.query(LogisticsETASnapshot)
        .filter(LogisticsETASnapshot.order_id == order_id)
        .order_by(LogisticsETASnapshot.computed_at.desc())
        .limit(limit)
        .all()
    )


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
        query = query.filter(LogisticsRiskSignal.vehicle_id == vehicle_id)
    if driver_id:
        query = query.filter(LogisticsRiskSignal.driver_id == driver_id)
    return query.order_by(LogisticsRiskSignal.ts.desc()).all()


def list_recent_deviation_events(
    db: Session,
    *,
    order_id: str,
    since: datetime,
) -> list[LogisticsDeviationEvent]:
    return (
        db.query(LogisticsDeviationEvent)
        .filter(LogisticsDeviationEvent.order_id == order_id)
        .filter(LogisticsDeviationEvent.ts >= since)
        .order_by(LogisticsDeviationEvent.ts.desc())
        .all()
    )


def update_order_timestamp(db: Session, *, order: LogisticsOrder) -> None:
    order.updated_at = datetime.now(tz=order.updated_at.tzinfo) if order.updated_at else datetime.utcnow()
