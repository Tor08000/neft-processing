from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditVisibility
from app.models.fuel import (
    FuelCard,
    FuelFraudSignal,
    FuelFraudSignalType,
    FuelStation,
    FuelTransaction,
    FuelTransactionStatus,
    StationReputationDaily,
)
from app.models.legal_graph import LegalEdgeType, LegalNodeType
from app.models.logistics import (
    FuelRouteLink,
    LogisticsDeviationEvent,
    LogisticsDeviationEventType,
    LogisticsOrder,
    LogisticsOrderStatus,
    LogisticsStopType,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.legal_graph.registry import LegalGraphRegistry
from app.services.logistics import repository as logistics_repository
from app.services.logistics.deviation import _haversine_m
from app.services.logistics.utils import ensure_aware

MSK_TZ = ZoneInfo("Europe/Moscow")

BURST_WINDOW_MINUTES = 15
BURST_CARD_THRESHOLD = 5
BURST_VOLUME_LITERS_THRESHOLD = 50
NIGHT_START_HOUR = 23
NIGHT_END_HOUR = 6
TANK_SANITY_MULTIPLIER = Decimal("1.2")


@dataclass(frozen=True)
class FraudSignalCandidate:
    signal_type: FuelFraudSignalType
    severity: int
    ts: datetime
    order_id: str | None
    vehicle_id: str | None
    driver_id: str | None
    station_id: str | None
    network_id: str | None
    explain: dict[str, Any]
    note: str | None = None


def evaluate_fraud_signals(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    card: FuelCard,
    station: FuelStation,
    vehicle_id: str | None,
    driver_id: str | None,
    occurred_at: datetime,
    volume_ml: int,
    amount_minor: int,
    request_vehicle_plate: str | None,
    request_driver_id: str | None,
    fuel_tx_id: str | None = None,
    include_current: bool = True,
) -> list[FraudSignalCandidate]:
    candidates: list[FraudSignalCandidate] = []
    order = _get_active_order(db, client_id=client_id, vehicle_id=vehicle_id, driver_id=driver_id)
    constraint = None
    route = None
    if order:
        route = logistics_repository.get_active_route(db, order_id=str(order.id))
        if route:
            constraint = logistics_repository.get_route_constraint(db, route_id=str(route.id))

    linked = False
    if fuel_tx_id:
        linked = (
            db.query(FuelRouteLink)
            .filter(FuelRouteLink.fuel_tx_id == fuel_tx_id)
            .one_or_none()
            is not None
        )

    off_route_recent = _find_recent_off_route(db, order_id=str(order.id) if order else None, occurred_at=occurred_at)
    off_route_strong = _find_recent_off_route(
        db,
        order_id=str(order.id) if order else None,
        occurred_at=occurred_at,
        window_minutes=30,
    )

    stop_info = None
    if order and route and constraint:
        stop_info = _nearest_stop_info(
            db,
            route_id=str(route.id),
            station=station,
            occurred_at=occurred_at,
            constraint=constraint,
        )

    if order and route and constraint and not linked:
        max_stop_radius = constraint.max_stop_radius_m
        nearest_distance = stop_info["distance_m"] if stop_info else None
        off_route_flag = bool(off_route_strong)
        if (
            nearest_distance is not None and nearest_distance > max_stop_radius * 3
        ) or off_route_flag:
            repeat = _has_recent_signal(
                db,
                client_id=client_id,
                vehicle_id=vehicle_id,
                driver_id=driver_id,
                signal_type=FuelFraudSignalType.FUEL_OFF_ROUTE_STRONG,
                since=occurred_at - timedelta(days=7),
            )
            severity = 85
            if _is_night(occurred_at):
                severity += 5
            if repeat:
                severity += 5
            candidates.append(
                FraudSignalCandidate(
                    signal_type=FuelFraudSignalType.FUEL_OFF_ROUTE_STRONG,
                    severity=min(severity, 100),
                    ts=occurred_at,
                    order_id=str(order.id),
                    vehicle_id=vehicle_id,
                    driver_id=driver_id,
                    station_id=str(station.id),
                    network_id=str(station.network_id),
                    explain={
                        "nearest_stop_distance_m": nearest_distance,
                        "time_delta_minutes": stop_info["time_delta_minutes"] if stop_info else None,
                        "off_route_state": off_route_flag,
                        "constraints": _constraint_payload(constraint),
                    },
                    note=_note_off_route(nearest_distance, off_route_flag),
                )
            )

    if order and route and constraint and stop_info and stop_info["stop"]:
        max_stop_radius = constraint.max_stop_radius_m
        distance = stop_info["distance_m"]
        if (
            stop_info["stop"].stop_type != LogisticsStopType.FUEL
            and distance is not None
            and distance > max_stop_radius * 2
        ):
            severity = 70
            if distance > max_stop_radius * 3:
                severity = 85
            else:
                severity = 75
            candidates.append(
                FraudSignalCandidate(
                    signal_type=FuelFraudSignalType.FUEL_STOP_MISMATCH_STRONG,
                    severity=severity,
                    ts=occurred_at,
                    order_id=str(order.id),
                    vehicle_id=vehicle_id,
                    driver_id=driver_id,
                    station_id=str(station.id),
                    network_id=str(station.network_id),
                    explain={
                        "stop_type": stop_info["stop"].stop_type.value,
                        "distance_to_stop_m": distance,
                        "time_delta_minutes": stop_info["time_delta_minutes"],
                        "constraints": _constraint_payload(constraint),
                    },
                    note=f"Stop type {stop_info['stop'].stop_type.value} with distance {distance}m",
                )
            )

    if off_route_recent:
        candidates.append(
            FraudSignalCandidate(
                signal_type=FuelFraudSignalType.ROUTE_DEVIATION_BEFORE_FUEL,
                severity=80,
                ts=occurred_at,
                order_id=str(order.id) if order else None,
                vehicle_id=vehicle_id,
                driver_id=driver_id,
                station_id=str(station.id),
                network_id=str(station.network_id),
                explain={
                    "off_route_ts": off_route_recent.ts.isoformat(),
                    "distance_from_route_m": off_route_recent.distance_from_route_m,
                },
                note="Off-route event within 60 minutes before fuel",
            )
        )

    mismatch_note = _driver_vehicle_mismatch_note(
        card=card,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        request_vehicle_plate=request_vehicle_plate,
        request_driver_id=request_driver_id,
        order=order,
    )
    if mismatch_note:
        candidates.append(
            FraudSignalCandidate(
                signal_type=FuelFraudSignalType.DRIVER_VEHICLE_MISMATCH,
                severity=75,
                ts=occurred_at,
                order_id=str(order.id) if order else None,
                vehicle_id=vehicle_id,
                driver_id=driver_id,
                station_id=str(station.id),
                network_id=str(station.network_id),
                explain={"mismatch": mismatch_note},
                note=mismatch_note,
            )
        )

    burst_candidate = _station_burst_signal(
        db,
        client_id=client_id,
        station_id=str(station.id),
        network_id=str(station.network_id),
        occurred_at=occurred_at,
        volume_ml=volume_ml,
        card_id=str(card.id),
        include_current=include_current,
    )
    if burst_candidate:
        candidates.append(burst_candidate)

    outlier_candidate = _station_outlier_signal(
        db,
        station_id=str(station.id),
        occurred_at=occurred_at,
        network_id=str(station.network_id),
    )
    if outlier_candidate:
        candidates.append(outlier_candidate)

    night_candidate = _night_repeat_signal(
        db,
        card_id=str(card.id),
        vehicle_id=vehicle_id,
        occurred_at=occurred_at,
        include_current=include_current,
    )
    if night_candidate:
        candidates.append(night_candidate)

    tank_candidate = _tank_sanity_repeat_signal(
        db,
        vehicle_id=vehicle_id,
        occurred_at=occurred_at,
        volume_ml=volume_ml,
        include_current=include_current,
    )
    if tank_candidate:
        candidates.append(tank_candidate)

    return candidates


def summarize_fraud_signals(
    db: Session,
    *,
    client_id: str,
    vehicle_id: str | None,
    driver_id: str | None,
    station_id: str | None,
    occurred_at: datetime,
    pending_signals: list[FraudSignalCandidate] | None = None,
) -> dict[str, Any]:
    pending_signals = pending_signals or []
    since_24h = occurred_at - timedelta(hours=24)
    since_7d = occurred_at - timedelta(days=7)

    query = db.query(FuelFraudSignal).filter(FuelFraudSignal.client_id == client_id)
    if vehicle_id:
        query = query.filter(FuelFraudSignal.vehicle_id == vehicle_id)
    elif driver_id:
        query = query.filter(FuelFraudSignal.driver_id == driver_id)
    elif station_id:
        query = query.filter(FuelFraudSignal.station_id == station_id)

    count_24h = query.filter(FuelFraudSignal.ts >= since_24h).count()
    count_7d = query.filter(FuelFraudSignal.ts >= since_7d).count()
    max_severity = (
        query.filter(FuelFraudSignal.ts >= since_24h)
        .with_entities(func.coalesce(func.max(FuelFraudSignal.severity), 0))
        .scalar()
        or 0
    )
    has_strong_off_route = (
        query.filter(FuelFraudSignal.ts >= since_24h)
        .filter(FuelFraudSignal.signal_type == FuelFraudSignalType.FUEL_OFF_ROUTE_STRONG)
        .count()
        > 0
    )

    for candidate in pending_signals:
        if candidate.ts >= since_24h:
            count_24h += 1
            max_severity = max(max_severity, candidate.severity)
            if candidate.signal_type == FuelFraudSignalType.FUEL_OFF_ROUTE_STRONG:
                has_strong_off_route = True
        if candidate.ts >= since_7d:
            count_7d += 1

    station_outlier_score = None
    if station_id:
        station_record = (
            db.query(StationReputationDaily)
            .filter(StationReputationDaily.station_id == station_id)
            .filter(StationReputationDaily.day == occurred_at.date())
            .one_or_none()
        )
        if station_record:
            station_outlier_score = station_record.outlier_score

    return {
        "signals_last_24h_count": count_24h,
        "signals_last_7d_count": count_7d,
        "max_signal_severity_24h": max_severity,
        "has_strong_off_route": has_strong_off_route,
        "station_outlier_score_today": station_outlier_score,
    }


def persist_fraud_signals(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    fuel_tx_id: str | None,
    candidates: list[FraudSignalCandidate],
    request_ctx: RequestContext | None = None,
) -> list[FuelFraudSignal]:
    saved: list[FuelFraudSignal] = []
    for candidate in candidates:
        signal = FuelFraudSignal(
            tenant_id=tenant_id,
            client_id=client_id,
            signal_type=candidate.signal_type,
            severity=candidate.severity,
            ts=candidate.ts,
            fuel_tx_id=fuel_tx_id,
            order_id=candidate.order_id,
            vehicle_id=candidate.vehicle_id,
            driver_id=candidate.driver_id,
            station_id=candidate.station_id,
            network_id=candidate.network_id,
            explain=candidate.explain,
        )
        db.add(signal)
        db.flush()
        saved.append(signal)
        AuditService(db).audit(
            event_type="FRAUD_SIGNAL_EMITTED",
            entity_type="fuel_fraud_signal",
            entity_id=str(signal.id),
            action="CREATE",
            visibility=AuditVisibility.INTERNAL,
            after={
                "signal_type": signal.signal_type.value,
                "severity": signal.severity,
                "fuel_tx_id": fuel_tx_id,
                "order_id": candidate.order_id,
                "station_id": candidate.station_id,
            },
            request_ctx=request_ctx,
        )
        _register_fraud_signal_graph(
            db,
            tenant_id=tenant_id,
            signal_id=str(signal.id),
            fuel_tx_id=fuel_tx_id,
            order_id=candidate.order_id,
            station_id=candidate.station_id,
            request_ctx=request_ctx,
        )
    if saved:
        db.commit()
    return saved


def fraud_signals_payload(candidates: list[FraudSignalCandidate], limit: int = 3) -> list[dict[str, Any]]:
    ordered = sorted(candidates, key=lambda item: item.severity, reverse=True)
    payload = []
    for candidate in ordered[:limit]:
        payload.append(
            {
                "type": candidate.signal_type.value,
                "severity": candidate.severity,
                "note": candidate.note,
            }
        )
    return payload


def compute_station_reputation_daily(
    db: Session,
    *,
    target_day: date,
    request_ctx: RequestContext | None = None,
) -> int:
    day_start = datetime.combine(target_day, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    stations = (
        db.query(FuelTransaction.station_id, FuelTransaction.network_id)
        .filter(FuelTransaction.occurred_at >= day_start)
        .filter(FuelTransaction.occurred_at < day_end)
        .distinct()
        .all()
    )
    upserts = 0
    for station_id, network_id in stations:
        txs = (
            db.query(FuelTransaction)
            .filter(FuelTransaction.station_id == station_id)
            .filter(FuelTransaction.occurred_at >= day_start)
            .filter(FuelTransaction.occurred_at < day_end)
            .all()
        )
        if not txs:
            continue
        tx_count = len(txs)
        decline_count = len([tx for tx in txs if tx.status == FuelTransactionStatus.DECLINED])
        risk_block_count = len(
            [
                tx
                for tx in txs
                if tx.status == FuelTransactionStatus.DECLINED
                and (tx.decline_code or "") == "RISK_BLOCK"
            ]
        )
        avg_liters = int(sum(tx.volume_ml for tx in txs) / max(tx_count, 1) / 1000)
        avg_amount = int(sum(tx.amount_total_minor for tx in txs) / max(tx_count, 1))

        baseline_start = target_day - timedelta(days=14)
        baseline_avg = (
            db.query(func.coalesce(func.avg(StationReputationDaily.tx_count), 0))
            .filter(StationReputationDaily.station_id == station_id)
            .filter(StationReputationDaily.day >= baseline_start)
            .filter(StationReputationDaily.day < target_day)
            .scalar()
            or 0
        )
        decline_rate = decline_count / tx_count if tx_count else 0
        outlier_score = 0
        if decline_rate > 0.2:
            outlier_score += 40
        if baseline_avg and tx_count > baseline_avg * 1.5:
            outlier_score += 30
        if avg_liters >= BURST_VOLUME_LITERS_THRESHOLD:
            outlier_score += 20
        outlier_score = min(outlier_score, 100)

        existing = (
            db.query(StationReputationDaily)
            .filter(StationReputationDaily.station_id == station_id)
            .filter(StationReputationDaily.day == target_day)
            .one_or_none()
        )
        if existing:
            existing.tx_count = tx_count
            existing.decline_count = decline_count
            existing.risk_block_count = risk_block_count
            existing.avg_liters = avg_liters
            existing.avg_amount = avg_amount
            existing.outlier_score = outlier_score
            record = existing
        else:
            record = StationReputationDaily(
                tenant_id=txs[0].tenant_id,
                network_id=network_id,
                station_id=station_id,
                day=target_day,
                tx_count=tx_count,
                decline_count=decline_count,
                risk_block_count=risk_block_count,
                avg_liters=avg_liters,
                avg_amount=avg_amount,
                outlier_score=outlier_score,
            )
            db.add(record)
        upserts += 1
        AuditService(db).audit(
            event_type="STATION_REPUTATION_COMPUTED",
            entity_type="station_reputation_daily",
            entity_id=str(record.id),
            action="UPSERT",
            visibility=AuditVisibility.INTERNAL,
            after={
                "station_id": str(station_id),
                "day": target_day.isoformat(),
                "outlier_score": outlier_score,
            },
            request_ctx=request_ctx,
        )

    if upserts:
        db.commit()
    return upserts


def cleanup_fraud_signals(db: Session, *, older_than: datetime) -> int:
    deleted = (
        db.query(FuelFraudSignal)
        .filter(FuelFraudSignal.ts < older_than)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def _get_active_order(
    db: Session,
    *,
    client_id: str,
    vehicle_id: str | None,
    driver_id: str | None,
) -> LogisticsOrder | None:
    query = db.query(LogisticsOrder).filter(LogisticsOrder.client_id == client_id)
    query = query.filter(LogisticsOrder.status == LogisticsOrderStatus.IN_PROGRESS)
    if vehicle_id:
        query = query.filter(LogisticsOrder.vehicle_id == vehicle_id)
    elif driver_id:
        query = query.filter(LogisticsOrder.driver_id == driver_id)
    return query.order_by(LogisticsOrder.updated_at.desc()).first()


def _nearest_stop_info(
    db: Session,
    *,
    route_id: str,
    station: FuelStation,
    occurred_at: datetime,
    constraint,
) -> dict[str, Any] | None:
    stops = logistics_repository.get_route_stops(db, route_id=route_id)
    if not stops:
        return None

    window_minutes = constraint.allowed_fuel_window_minutes
    occurred_at = ensure_aware(occurred_at) or occurred_at
    start_at = occurred_at - timedelta(minutes=window_minutes)
    end_at = occurred_at + timedelta(minutes=window_minutes)
    nearby_stops = []
    for stop in stops:
        candidate_times = [
            ensure_aware(stop.planned_arrival_at),
            ensure_aware(stop.actual_arrival_at),
            ensure_aware(stop.actual_departure_at),
        ]
        if any(timestamp and start_at <= timestamp <= end_at for timestamp in candidate_times):
            nearby_stops.append(stop)

    station_lat = float(station.lat) if station.lat else None
    station_lon = float(station.lon) if station.lon else None

    matched_stop = None
    min_distance = None
    if station_lat is not None and station_lon is not None:
        for stop in nearby_stops:
            if stop.lat is None or stop.lon is None:
                continue
            distance = _haversine_m(station_lat, station_lon, float(stop.lat), float(stop.lon))
            if min_distance is None or distance < min_distance:
                min_distance = distance
                matched_stop = stop

    if matched_stop is None and stops:
        nearest_by_time = sorted(
            stops,
            key=lambda stop: abs(
                int(
                    (occurred_at - (stop.planned_arrival_at or occurred_at)).total_seconds()
                    / 60
                )
            ),
        )
        matched_stop = nearest_by_time[0]

    preferred_time = ensure_aware(_preferred_stop_time(matched_stop)) if matched_stop else None
    time_delta = _time_delta_minutes(occurred_at, preferred_time) if matched_stop else None
    if matched_stop and min_distance is None and time_delta is not None and time_delta > window_minutes:
        matched_stop = None

    return {
        "stop": matched_stop,
        "distance_m": int(min_distance) if min_distance is not None else None,
        "time_delta_minutes": time_delta,
        "stop_candidates": len(nearby_stops),
    }


def _find_recent_off_route(
    db: Session,
    *,
    order_id: str | None,
    occurred_at: datetime,
    window_minutes: int = 60,
) -> LogisticsDeviationEvent | None:
    if not order_id:
        return None
    since = occurred_at - timedelta(minutes=window_minutes)
    return (
        db.query(LogisticsDeviationEvent)
        .filter(LogisticsDeviationEvent.order_id == order_id)
        .filter(LogisticsDeviationEvent.event_type == LogisticsDeviationEventType.OFF_ROUTE)
        .filter(LogisticsDeviationEvent.ts >= since)
        .filter(LogisticsDeviationEvent.ts <= occurred_at)
        .order_by(LogisticsDeviationEvent.ts.desc())
        .first()
    )


def _has_recent_signal(
    db: Session,
    *,
    client_id: str,
    vehicle_id: str | None,
    driver_id: str | None,
    signal_type: FuelFraudSignalType,
    since: datetime,
) -> bool:
    query = (
        db.query(FuelFraudSignal)
        .filter(FuelFraudSignal.client_id == client_id)
        .filter(FuelFraudSignal.signal_type == signal_type)
        .filter(FuelFraudSignal.ts >= since)
    )
    if vehicle_id:
        query = query.filter(FuelFraudSignal.vehicle_id == vehicle_id)
    if driver_id:
        query = query.filter(FuelFraudSignal.driver_id == driver_id)
    return query.count() > 0


def _constraint_payload(constraint) -> dict[str, Any] | None:
    if not constraint:
        return None
    return {
        "max_stop_radius_m": constraint.max_stop_radius_m,
        "allowed_fuel_window_minutes": constraint.allowed_fuel_window_minutes,
    }


def _time_delta_minutes(occurred_at: datetime, planned_at: datetime | None) -> int | None:
    if planned_at is None:
        return None
    return int(abs((occurred_at - planned_at).total_seconds() / 60))


def _preferred_stop_time(stop) -> datetime | None:
    if not stop:
        return None
    return stop.actual_arrival_at or stop.actual_departure_at or stop.planned_arrival_at


def _is_night(occurred_at: datetime) -> bool:
    local_time = occurred_at.astimezone(MSK_TZ)
    return local_time.hour >= NIGHT_START_HOUR or local_time.hour < NIGHT_END_HOUR


def _note_off_route(distance_m: int | None, off_route: bool) -> str:
    if off_route and distance_m is not None:
        return f"No matching stop within {distance_m}m; off-route confirmed"
    if off_route:
        return "Off-route confirmed prior to fuel"
    if distance_m is None:
        return "No matching stop within route constraints"
    return f"No matching stop within {distance_m}m"


def _driver_vehicle_mismatch_note(
    *,
    card: FuelCard,
    vehicle_id: str | None,
    driver_id: str | None,
    request_vehicle_plate: str | None,
    request_driver_id: str | None,
    order: LogisticsOrder | None,
) -> str | None:
    if card.vehicle_id and request_vehicle_plate and vehicle_id and str(card.vehicle_id) != vehicle_id:
        return "Vehicle mismatch for card assignment"
    if card.driver_id and request_driver_id and driver_id and str(card.driver_id) != driver_id:
        return "Driver mismatch for card assignment"
    if order and order.vehicle_id and vehicle_id and str(order.vehicle_id) != vehicle_id:
        return "Order vehicle mismatch for fuel attempt"
    if order and order.driver_id and driver_id and str(order.driver_id) != driver_id:
        return "Order driver mismatch for fuel attempt"
    return None


def _station_burst_signal(
    db: Session,
    *,
    client_id: str,
    station_id: str,
    network_id: str | None,
    occurred_at: datetime,
    volume_ml: int,
    card_id: str,
    include_current: bool,
) -> FraudSignalCandidate | None:
    since = occurred_at - timedelta(minutes=BURST_WINDOW_MINUTES)
    transactions = (
        db.query(FuelTransaction.card_id, FuelTransaction.volume_ml)
        .filter(FuelTransaction.client_id == client_id)
        .filter(FuelTransaction.station_id == station_id)
        .filter(FuelTransaction.occurred_at >= since)
        .filter(FuelTransaction.occurred_at <= occurred_at)
        .all()
    )
    card_ids = {str(row[0]) for row in transactions}
    total_volume = sum(row[1] for row in transactions)
    count = len(transactions)

    if include_current:
        card_ids.add(card_id)
        total_volume += volume_ml
        count += 1

    distinct_cards = len(card_ids)
    avg_liters = (total_volume / max(count, 1)) / 1000
    if distinct_cards < BURST_CARD_THRESHOLD or avg_liters < BURST_VOLUME_LITERS_THRESHOLD:
        return None

    severity = 70 + min((distinct_cards - BURST_CARD_THRESHOLD) * 5, 20)
    return FraudSignalCandidate(
        signal_type=FuelFraudSignalType.MULTI_CARD_SAME_STATION_BURST,
        severity=min(severity, 90),
        ts=occurred_at,
        order_id=None,
        vehicle_id=None,
        driver_id=None,
        station_id=station_id,
        network_id=network_id,
        explain={
            "card_count": distinct_cards,
            "avg_liters": round(avg_liters, 2),
            "window_minutes": BURST_WINDOW_MINUTES,
        },
        note=f"{distinct_cards} cards used at same station within {BURST_WINDOW_MINUTES}m",
    )


def _station_outlier_signal(
    db: Session,
    *,
    station_id: str,
    occurred_at: datetime,
    network_id: str | None,
) -> FraudSignalCandidate | None:
    record = (
        db.query(StationReputationDaily)
        .filter(StationReputationDaily.station_id == station_id)
        .filter(StationReputationDaily.day == occurred_at.date())
        .one_or_none()
    )
    if not record or record.outlier_score <= 80:
        return None

    baseline = (
        db.query(func.coalesce(func.avg(StationReputationDaily.tx_count), 0))
        .filter(StationReputationDaily.station_id == station_id)
        .filter(StationReputationDaily.day >= occurred_at.date() - timedelta(days=14))
        .filter(StationReputationDaily.day < occurred_at.date())
        .scalar()
        or 0
    )
    if baseline and record.tx_count <= baseline:
        return None

    severity = 70 + min(int((record.outlier_score - 80) * 1.25), 25)
    return FraudSignalCandidate(
        signal_type=FuelFraudSignalType.STATION_OUTLIER_CLUSTER,
        severity=min(severity, 95),
        ts=occurred_at,
        order_id=None,
        vehicle_id=None,
        driver_id=None,
        station_id=station_id,
        network_id=network_id,
        explain={
            "outlier_score": record.outlier_score,
            "tx_count": record.tx_count,
            "baseline_tx_count": baseline,
        },
        note="Station flagged as outlier cluster",
    )


def _night_repeat_signal(
    db: Session,
    *,
    card_id: str,
    vehicle_id: str | None,
    occurred_at: datetime,
    include_current: bool,
) -> FraudSignalCandidate | None:
    if not _is_night(occurred_at):
        return None
    since = occurred_at - timedelta(days=7)
    query = db.query(FuelTransaction).filter(FuelTransaction.occurred_at >= since)
    query = query.filter(FuelTransaction.occurred_at <= occurred_at)
    if vehicle_id:
        query = query.filter(FuelTransaction.vehicle_id == vehicle_id)
    else:
        query = query.filter(FuelTransaction.card_id == card_id)
    transactions = query.all()
    count = sum(1 for tx in transactions if _is_night(tx.occurred_at))
    if include_current:
        count += 1
    if count < 3:
        return None
    severity = 65 + min((count - 3) * 5, 20)
    return FraudSignalCandidate(
        signal_type=FuelFraudSignalType.REPEATED_NIGHT_REFUEL,
        severity=min(severity, 85),
        ts=occurred_at,
        order_id=None,
        vehicle_id=vehicle_id,
        driver_id=None,
        station_id=None,
        network_id=None,
        explain={"count_7d": count, "night_hours": [NIGHT_START_HOUR, NIGHT_END_HOUR]},
        note=f"Night refuel repeated {count} times in 7 days",
    )


def _tank_sanity_repeat_signal(
    db: Session,
    *,
    vehicle_id: str | None,
    occurred_at: datetime,
    volume_ml: int,
    include_current: bool,
) -> FraudSignalCandidate | None:
    if not vehicle_id:
        return None
    capacity_ml = None
    from app.models.fleet import FleetVehicle

    record = db.query(FleetVehicle).filter(FleetVehicle.id == vehicle_id).one_or_none()
    if record and record.tank_capacity_liters:
        capacity_ml = int(Decimal(record.tank_capacity_liters) * Decimal("1000"))
    if not capacity_ml:
        return None

    threshold = int(Decimal(capacity_ml) * TANK_SANITY_MULTIPLIER)
    since = occurred_at - timedelta(days=30)
    count = (
        db.query(FuelTransaction)
        .filter(FuelTransaction.vehicle_id == vehicle_id)
        .filter(FuelTransaction.occurred_at >= since)
        .filter(FuelTransaction.occurred_at <= occurred_at)
        .filter(FuelTransaction.volume_ml > threshold)
        .count()
    )
    if include_current and volume_ml > threshold:
        count += 1
    if count < 2:
        return None
    return FraudSignalCandidate(
        signal_type=FuelFraudSignalType.TANK_SANITY_REPEAT,
        severity=80,
        ts=occurred_at,
        order_id=None,
        vehicle_id=vehicle_id,
        driver_id=None,
        station_id=None,
        network_id=None,
        explain={"count_30d": count, "capacity_ml": capacity_ml, "threshold_ml": threshold},
        note="Tank sanity exceeded multiple times",
    )


def _register_fraud_signal_graph(
    db: Session,
    *,
    tenant_id: int,
    signal_id: str,
    fuel_tx_id: str | None,
    order_id: str | None,
    station_id: str | None,
    request_ctx: RequestContext | None,
) -> None:
    registry = LegalGraphRegistry(db, request_ctx=request_ctx)
    signal_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.FRAUD_SIGNAL,
        ref_id=signal_id,
        ref_table="fuel_fraud_signals",
    ).node
    if fuel_tx_id:
        fuel_node = registry.get_or_create_node(
            tenant_id=tenant_id,
            node_type=LegalNodeType.FUEL_TRANSACTION,
            ref_id=fuel_tx_id,
            ref_table="fuel_transactions",
        ).node
        registry.link(
            tenant_id=tenant_id,
            src_node_id=str(fuel_node.id),
            dst_node_id=str(signal_node.id),
            edge_type=LegalEdgeType.RELATES_TO,
            meta={"relation": "FUEL_TX_RELATES_TO_FRAUD_SIGNAL"},
        )
    if order_id:
        order_node = registry.get_or_create_node(
            tenant_id=tenant_id,
            node_type=LegalNodeType.LOGISTICS_ORDER,
            ref_id=order_id,
            ref_table="logistics_orders",
        ).node
        registry.link(
            tenant_id=tenant_id,
            src_node_id=str(order_node.id),
            dst_node_id=str(signal_node.id),
            edge_type=LegalEdgeType.RELATES_TO,
            meta={"relation": "ORDER_RELATES_TO_FRAUD_SIGNAL"},
        )
    if station_id:
        station_node = registry.get_or_create_node(
            tenant_id=tenant_id,
            node_type=LegalNodeType.FUEL_STATION,
            ref_id=station_id,
            ref_table="fuel_stations",
        ).node
        registry.link(
            tenant_id=tenant_id,
            src_node_id=str(station_node.id),
            dst_node_id=str(signal_node.id),
            edge_type=LegalEdgeType.RELATES_TO,
            meta={"relation": "STATION_RELATES_TO_FRAUD_SIGNAL"},
        )


__all__ = [
    "FraudSignalCandidate",
    "cleanup_fraud_signals",
    "compute_station_reputation_daily",
    "evaluate_fraud_signals",
    "fraud_signals_payload",
    "persist_fraud_signals",
    "summarize_fraud_signals",
]
