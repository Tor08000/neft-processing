from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import radians, sin, cos, sqrt, atan2

from sqlalchemy import func
from sqlalchemy.orm import Session, load_only

from app.models.fuel import FuelStation, FuelTransaction
from app.models.logistics import (
    LogisticsFuelAlert,
    LogisticsFuelAlertSeverity,
    LogisticsFuelAlertStatus,
    LogisticsFuelAlertType,
    LogisticsFuelLink,
    LogisticsFuelLinkedBy,
    LogisticsFuelLinkReason,
    LogisticsOrder,
    LogisticsRoute,
    LogisticsStop,
    LogisticsTrackingEvent,
)
from app.services.logistics.repository import id_equals, ids_match, refresh_by_id


@dataclass(frozen=True)
class FuelLinkerStats:
    processed: int
    linked: int
    unlinked: int
    alerts_created: int


@dataclass(frozen=True)
class CandidateResult:
    trip: LogisticsOrder
    score: int
    reason: LogisticsFuelLinkReason
    distance_km: float | None


AVG_CONSUMPTION_L_PER_100KM = 12.0

_FUEL_TX_PORTAL_COLUMNS = (
    FuelTransaction.id,
    FuelTransaction.client_id,
    FuelTransaction.card_id,
    FuelTransaction.vehicle_id,
    FuelTransaction.driver_id,
    FuelTransaction.station_id,
    FuelTransaction.network_id,
    FuelTransaction.occurred_at,
    FuelTransaction.fuel_type,
    FuelTransaction.volume_ml,
    FuelTransaction.volume_liters,
    FuelTransaction.amount_total_minor,
    FuelTransaction.merchant_name,
    FuelTransaction.location,
)


def _fuel_tx_query(db: Session):
    # Client logistics portal reads must stay compatible with shared storage
    # where newer ORM-only columns may not exist yet.
    return db.query(FuelTransaction).options(load_only(*_FUEL_TX_PORTAL_COLUMNS))


def _get_fuel_tx(db: Session, *, fuel_tx_id: str) -> FuelTransaction | None:
    return _fuel_tx_query(db).filter(FuelTransaction.id == fuel_tx_id).one_or_none()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _trip_window(order: LogisticsOrder) -> tuple[datetime | None, datetime | None]:
    start = order.actual_start_at or order.planned_start_at
    end = order.actual_end_at or order.planned_end_at
    return start, end


def _nearest_distance_to_trip(db: Session, trip_id: str, lat: float, lon: float) -> float | None:
    stops = (
        db.query(LogisticsStop)
        .join(LogisticsRoute, ids_match(LogisticsRoute.id, LogisticsStop.route_id))
        .filter(id_equals(LogisticsRoute.order_id, trip_id))
        .all()
    )
    tracking = (
        db.query(LogisticsTrackingEvent)
        .filter(id_equals(LogisticsTrackingEvent.order_id, trip_id))
        .order_by(LogisticsTrackingEvent.ts.desc())
        .limit(200)
        .all()
    )
    distances: list[float] = []
    for stop in stops:
        if stop.lat is not None and stop.lon is not None:
            distances.append(_haversine_km(lat, lon, float(stop.lat), float(stop.lon)))
    for event in tracking:
        if event.lat is not None and event.lon is not None:
            distances.append(_haversine_km(lat, lon, float(event.lat), float(event.lon)))
    return min(distances) if distances else None


def _candidate_for_tx(db: Session, tx: FuelTransaction, trip: LogisticsOrder) -> CandidateResult | None:
    start, end = _trip_window(trip)
    if not start or not end:
        return None

    extended_start = start - timedelta(hours=2)
    extended_end = end + timedelta(hours=2)
    if not (extended_start <= tx.occurred_at <= extended_end):
        return None

    score = 0
    reason = LogisticsFuelLinkReason.TIME_WINDOW_MATCH
    if start <= tx.occurred_at <= end:
        score += 40
    else:
        score += 20

    station = db.query(FuelStation).filter(FuelStation.id == tx.station_id).one_or_none()
    distance_km: float | None = None
    if station and station.lat and station.lon:
        distance_km = _nearest_distance_to_trip(db, str(trip.id), float(station.lat), float(station.lon))
        if distance_km is not None:
            if distance_km <= 3:
                score += 40
                reason = LogisticsFuelLinkReason.ROUTE_PROXIMITY_MATCH
            elif distance_km <= 10:
                score += 20
                reason = LogisticsFuelLinkReason.ROUTE_PROXIMITY_MATCH
            if distance_km <= 3:
                score += 20
                reason = LogisticsFuelLinkReason.STATION_ON_ROUTE

    return CandidateResult(trip=trip, score=min(100, score), reason=reason, distance_km=distance_km)


def run_linker(
    db: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    client_id: str | None = None,
) -> FuelLinkerStats:
    query = (
        _fuel_tx_query(db)
        .filter(FuelTransaction.occurred_at >= date_from)
        .filter(FuelTransaction.occurred_at <= date_to)
    )
    if client_id:
        query = query.filter(FuelTransaction.client_id == client_id)
    txs = query.order_by(FuelTransaction.occurred_at.asc()).all()
    linked = 0
    unlinked = 0
    alerts_created = 0

    for tx in txs:
        if db.query(LogisticsFuelLink).filter(LogisticsFuelLink.fuel_tx_id == tx.id).first():
            continue
        trips = (
            db.query(LogisticsOrder)
            .filter(LogisticsOrder.client_id == tx.client_id)
            .order_by(LogisticsOrder.created_at.desc())
            .limit(20)
            .all()
        )
        candidates = [c for c in (_candidate_for_tx(db, tx, trip) for trip in trips) if c is not None]
        if not candidates:
            unlinked += 1
            _create_out_of_time_alert(db, tx, None)
            alerts_created += 1
            continue

        candidates.sort(
            key=lambda c: (
                -c.score,
                abs((tx.occurred_at - ((_trip_window(c.trip)[0] or tx.occurred_at) + ((_trip_window(c.trip)[1] or tx.occurred_at) - (_trip_window(c.trip)[0] or tx.occurred_at)) / 2)).total_seconds()),
            )
        )
        best = candidates[0]
        if best.score >= 60:
            db.add(
                LogisticsFuelLink(
                    client_id=tx.client_id,
                    trip_id=str(best.trip.id),
                    fuel_tx_id=str(tx.id),
                    score=best.score,
                    reason=best.reason,
                    linked_by=LogisticsFuelLinkedBy.SYSTEM,
                )
            )
            linked += 1
            if best.distance_km is not None and best.distance_km > 10:
                db.add(
                    LogisticsFuelAlert(
                        client_id=tx.client_id,
                        trip_id=str(best.trip.id),
                        fuel_tx_id=str(tx.id),
                        type=LogisticsFuelAlertType.OUT_OF_ROUTE,
                        severity=LogisticsFuelAlertSeverity.CRITICAL,
                        title="Fuel transaction is out of route",
                        details="Detected fuel station far from route/track",
                        evidence={"distance_km": round(best.distance_km, 2)},
                        status=LogisticsFuelAlertStatus.OPEN,
                    )
                )
                alerts_created += 1
        else:
            unlinked += 1
            _create_out_of_time_alert(db, tx, best.trip)
            alerts_created += 1

    db.commit()

    alerts_created += _create_high_consumption_alerts(db, date_from=date_from, date_to=date_to)
    db.commit()

    return FuelLinkerStats(processed=len(txs), linked=linked, unlinked=unlinked, alerts_created=alerts_created)


def _create_out_of_time_alert(db: Session, tx: FuelTransaction, trip: LogisticsOrder | None) -> None:
    delta_minutes = None
    if trip:
        start, end = _trip_window(trip)
        if start and tx.occurred_at < start:
            delta_minutes = int((start - tx.occurred_at).total_seconds() / 60)
        elif end and tx.occurred_at > end:
            delta_minutes = int((tx.occurred_at - end).total_seconds() / 60)
    db.add(
        LogisticsFuelAlert(
            client_id=tx.client_id,
            trip_id=str(trip.id) if trip else None,
            fuel_tx_id=str(tx.id),
            type=LogisticsFuelAlertType.OUT_OF_TIME_WINDOW,
            severity=LogisticsFuelAlertSeverity.WARN,
            title="Fuel transaction is out of trip time window",
            details="No matching trip was found in expected time window",
            evidence={"delta_minutes": delta_minutes},
            status=LogisticsFuelAlertStatus.OPEN,
        )
    )


def _trip_distance_km(db: Session, trip_id: str) -> float:
    route = (
        db.query(LogisticsRoute)
        .filter(id_equals(LogisticsRoute.order_id, trip_id))
        .order_by(LogisticsRoute.version.desc())
        .first()
    )
    return float(route.distance_km or 0)


def _create_high_consumption_alerts(db: Session, *, date_from: datetime, date_to: datetime) -> int:
    created = 0
    links = (
        db.query(LogisticsFuelLink)
        .filter(LogisticsFuelLink.created_at >= date_from)
        .filter(LogisticsFuelLink.created_at <= date_to)
        .all()
    )
    trip_ids = {str(link.trip_id) for link in links}
    for trip_id in trip_ids:
        trip_links = [link for link in links if str(link.trip_id) == trip_id]
        liters = 0.0
        for link in trip_links:
            tx = _get_fuel_tx(db, fuel_tx_id=str(link.fuel_tx_id))
            if tx and tx.volume_liters is not None:
                liters += float(tx.volume_liters)
            elif tx:
                liters += float(tx.volume_ml or 0) / 1000
        expected = _trip_distance_km(db, trip_id) * AVG_CONSUMPTION_L_PER_100KM / 100
        if expected <= 0:
            continue
        ratio = liters / expected
        if ratio <= 1.5:
            continue
        severity = LogisticsFuelAlertSeverity.CRITICAL if ratio > 2 else LogisticsFuelAlertSeverity.WARN
        first_tx_id = str(trip_links[0].fuel_tx_id)
        if db.query(LogisticsFuelAlert).filter(
            LogisticsFuelAlert.trip_id == trip_id,
            LogisticsFuelAlert.type == LogisticsFuelAlertType.HIGH_CONSUMPTION,
            LogisticsFuelAlert.fuel_tx_id == first_tx_id,
        ).first():
            continue
        db.add(
            LogisticsFuelAlert(
                client_id=trip_links[0].client_id,
                trip_id=trip_id,
                fuel_tx_id=first_tx_id,
                type=LogisticsFuelAlertType.HIGH_CONSUMPTION,
                severity=severity,
                title="High fuel consumption detected",
                details="Fuel volume for trip exceeds expected baseline",
                evidence={"liters": round(liters, 2), "expected_liters": round(expected, 2), "ratio": round(ratio, 2)},
                status=LogisticsFuelAlertStatus.OPEN,
            )
        )
        created += 1
    return created


def list_unlinked(
    db: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    limit: int,
    offset: int,
    client_id: str | None = None,
) -> list[dict]:
    query = (
        _fuel_tx_query(db)
        .filter(FuelTransaction.occurred_at >= date_from)
        .filter(FuelTransaction.occurred_at <= date_to)
    )
    if client_id:
        query = query.filter(FuelTransaction.client_id == client_id)
    txs = query.order_by(FuelTransaction.occurred_at.desc()).offset(offset).limit(limit).all()
    items: list[dict] = []
    for tx in txs:
        if db.query(LogisticsFuelLink).filter(LogisticsFuelLink.fuel_tx_id == tx.id).first():
            continue
        trips = db.query(LogisticsOrder).filter(LogisticsOrder.client_id == tx.client_id).order_by(LogisticsOrder.created_at.desc()).limit(20).all()
        best = None
        for trip in trips:
            cand = _candidate_for_tx(db, tx, trip)
            if cand and (best is None or cand.score > best.score):
                best = cand
        items.append(
            {
                "fuel_tx_id": str(tx.id),
                "ts": tx.occurred_at,
                "liters": float(tx.volume_liters) if tx.volume_liters is not None else float(tx.volume_ml or 0) / 1000,
                "amount": float(tx.amount_total_minor or 0),
                "station": tx.merchant_name or tx.location,
                "best_match_trip": str(best.trip.id) if best else None,
                "best_score": best.score if best else 0,
                "reason": best.reason.value if best else "NO_CANDIDATE",
            }
        )
    return items


def link_manually(db: Session, *, trip_id: str, fuel_tx_id: str) -> LogisticsFuelLink:
    trip_id = str(trip_id)
    existing = db.query(LogisticsFuelLink).filter(LogisticsFuelLink.fuel_tx_id == fuel_tx_id).one_or_none()
    if existing:
        return existing
    tx = _fuel_tx_query(db).filter(FuelTransaction.id == fuel_tx_id).one()
    link = LogisticsFuelLink(
        client_id=tx.client_id,
        trip_id=trip_id,
        fuel_tx_id=fuel_tx_id,
        score=100,
        reason=LogisticsFuelLinkReason.MANUAL_LINK,
        linked_by=LogisticsFuelLinkedBy.USER,
    )
    db.add(link)
    db.flush()
    link_id = str(link.id)
    db.commit()
    link = refresh_by_id(db, link, LogisticsFuelLink, link_id)
    return link


def unlink(db: Session, *, fuel_tx_id: str) -> None:
    db.query(LogisticsFuelLink).filter(LogisticsFuelLink.fuel_tx_id == fuel_tx_id).delete()
    db.commit()


def trip_fuel(db: Session, *, trip_id: str) -> dict:
    trip_id = str(trip_id)
    links = db.query(LogisticsFuelLink).filter(LogisticsFuelLink.trip_id == trip_id).order_by(LogisticsFuelLink.created_at.desc()).all()
    items = []
    liters_total = 0.0
    amount_total = 0.0
    for link in links:
        tx = _get_fuel_tx(db, fuel_tx_id=str(link.fuel_tx_id))
        if not tx:
            continue
        liters = float(tx.volume_liters) if tx.volume_liters is not None else float(tx.volume_ml or 0) / 1000
        amount = float(tx.amount_total_minor or 0)
        liters_total += liters
        amount_total += amount
        items.append(
            {
                "fuel_tx_id": str(tx.id),
                "ts": tx.occurred_at,
                "liters": liters,
                "amount": amount,
                "station": tx.merchant_name or tx.location,
                "score": link.score,
                "reason": link.reason,
            }
        )
    alerts = db.query(LogisticsFuelAlert).filter(LogisticsFuelAlert.trip_id == trip_id).order_by(LogisticsFuelAlert.created_at.desc()).all()
    return {
        "trip_id": trip_id,
        "items": items,
        "totals": {"liters": round(liters_total, 3), "amount": round(amount_total, 2)},
        "alerts": alerts,
    }


def fuel_alerts(
    db: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    type_: LogisticsFuelAlertType | None,
    severity: LogisticsFuelAlertSeverity | None,
    status: LogisticsFuelAlertStatus | None,
    limit: int,
    offset: int,
    client_id: str | None = None,
) -> tuple[list[LogisticsFuelAlert], int]:
    q = db.query(LogisticsFuelAlert).filter(LogisticsFuelAlert.created_at >= date_from, LogisticsFuelAlert.created_at <= date_to)
    if client_id:
        q = q.filter(LogisticsFuelAlert.client_id == client_id)
    if type_:
        q = q.filter(LogisticsFuelAlert.type == type_)
    if severity:
        q = q.filter(LogisticsFuelAlert.severity == severity)
    if status:
        q = q.filter(LogisticsFuelAlert.status == status)
    total = q.count()
    items = q.order_by(LogisticsFuelAlert.created_at.desc()).offset(offset).limit(limit).all()
    return items, total


def fuel_report(
    db: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    group_by: str,
    client_id: str | None = None,
) -> list[dict]:
    query = db.query(LogisticsFuelLink).filter(
        LogisticsFuelLink.created_at >= date_from,
        LogisticsFuelLink.created_at <= date_to,
    )
    if client_id:
        query = query.filter(LogisticsFuelLink.client_id == client_id)
    links = query.all()
    buckets: dict[str, dict] = {}
    for link in links:
        trip = db.query(LogisticsOrder).filter(id_equals(LogisticsOrder.id, str(link.trip_id))).one_or_none()
        tx = _get_fuel_tx(db, fuel_tx_id=str(link.fuel_tx_id))
        if not trip or not tx:
            continue
        if group_by == "vehicle":
            key = str(trip.vehicle_id or "unknown")
        elif group_by == "driver":
            key = str(trip.driver_id or "unknown")
        else:
            key = str(trip.id)
        bucket = buckets.setdefault(key, {"group": key, "liters": 0.0, "amount": 0.0, "tx_count": 0, "alerts_count": 0})
        bucket["liters"] += float(tx.volume_liters) if tx.volume_liters is not None else float(tx.volume_ml or 0) / 1000
        bucket["amount"] += float(tx.amount_total_minor or 0)
        bucket["tx_count"] += 1
    for key, bucket in buckets.items():
        bucket["alerts_count"] = db.query(func.count(LogisticsFuelAlert.id)).filter(LogisticsFuelAlert.trip_id == (None if group_by != "trip" else str(key))).scalar() or 0
    return list(buckets.values())
