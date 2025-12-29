from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fleet_intelligence import FIDriverDaily, FIStationDaily, FIVehicleDaily
from app.models.fuel import FuelFraudSignal, FuelFraudSignalType, FuelTransaction, FuelTransactionStatus
from app.models.logistics import LogisticsDeviationEvent, LogisticsDeviationEventType, LogisticsOrder, LogisticsRouteSnapshot
from app.models.fuel import StationReputationDaily
from app.schemas.fuel import DeclineCode
from app.services.fleet_intelligence import repository


MSK_TZ = ZoneInfo("Europe/Moscow")
NIGHT_HOURS = set(range(23, 24)) | set(range(0, 6))


def compute_daily_aggregates(
    db: Session,
    *,
    day: date,
    tz: ZoneInfo = MSK_TZ,
) -> dict[str, list]:
    start_at = datetime.combine(day, time.min, tzinfo=tz)
    end_at = start_at + timedelta(days=1)
    fuel_txs = (
        db.query(FuelTransaction)
        .filter(FuelTransaction.occurred_at >= start_at)
        .filter(FuelTransaction.occurred_at < end_at)
        .filter(
            FuelTransaction.status.in_(
                [
                    FuelTransactionStatus.AUTHORIZED,
                    FuelTransactionStatus.REVIEW_REQUIRED,
                    FuelTransactionStatus.SETTLED,
                    FuelTransactionStatus.DECLINED,
                ]
            )
        )
        .all()
    )

    driver_rollups: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    vehicle_rollups: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    station_rollups: dict[str, dict] = defaultdict(lambda: defaultdict(int))

    for tx in fuel_txs:
        local_ts = tx.occurred_at.astimezone(tz)
        is_night = local_ts.hour in NIGHT_HOURS
        if tx.driver_id:
            driver_bucket = driver_rollups[str(tx.driver_id)]
            driver_bucket.update(
                {
                    "tenant_id": tx.tenant_id,
                    "client_id": tx.client_id,
                    "driver_id": str(tx.driver_id),
                    "day": day,
                }
            )
            driver_bucket["fuel_tx_count"] += 1
            driver_bucket["fuel_volume_ml"] += int(tx.volume_ml)
            driver_bucket["fuel_amount_minor"] += int(tx.amount_total_minor)
            if is_night:
                driver_bucket["night_fuel_tx_count"] += 1
            if tx.status == FuelTransactionStatus.REVIEW_REQUIRED:
                driver_bucket["review_required_count"] += 1
            if tx.decline_code == DeclineCode.RISK_BLOCK.value:
                driver_bucket["risk_block_count"] += 1

        if tx.vehicle_id:
            vehicle_bucket = vehicle_rollups[str(tx.vehicle_id)]
            vehicle_bucket.update(
                {
                    "tenant_id": tx.tenant_id,
                    "client_id": tx.client_id,
                    "vehicle_id": str(tx.vehicle_id),
                    "day": day,
                }
            )
            vehicle_bucket["fuel_volume_ml"] += int(tx.volume_ml)
            vehicle_bucket["fuel_amount_minor"] += int(tx.amount_total_minor)

        station_bucket = station_rollups[str(tx.station_id)]
        station_bucket.update(
            {
                "tenant_id": tx.tenant_id,
                "network_id": str(tx.network_id) if tx.network_id else None,
                "station_id": str(tx.station_id),
                "day": day,
            }
        )
        station_bucket["tx_count"] += 1
        station_bucket.setdefault("card_ids", set()).add(str(tx.card_id))
        if tx.driver_id:
            station_bucket.setdefault("driver_ids", set()).add(str(tx.driver_id))
        station_bucket.setdefault("volume_sum_ml", 0)
        station_bucket.setdefault("amount_sum_minor", 0)
        station_bucket["volume_sum_ml"] += int(tx.volume_ml)
        station_bucket["amount_sum_minor"] += int(tx.amount_total_minor)
        if tx.status == FuelTransactionStatus.DECLINED:
            station_bucket["decline_count"] += 1
        if tx.decline_code == DeclineCode.RISK_BLOCK.value:
            station_bucket["risk_block_count"] += 1

    off_route_signals = (
        db.query(FuelFraudSignal)
        .filter(FuelFraudSignal.ts >= start_at)
        .filter(FuelFraudSignal.ts < end_at)
        .filter(FuelFraudSignal.signal_type == FuelFraudSignalType.FUEL_OFF_ROUTE_STRONG)
        .all()
    )
    for signal in off_route_signals:
        if signal.driver_id:
            driver_rollups[str(signal.driver_id)]["off_route_fuel_count"] += 1
        if signal.vehicle_id:
            vehicle_rollups[str(signal.vehicle_id)]["off_route_count"] += 1

    tank_sanity_signals = (
        db.query(FuelFraudSignal)
        .filter(FuelFraudSignal.ts >= start_at)
        .filter(FuelFraudSignal.ts < end_at)
        .filter(FuelFraudSignal.signal_type == FuelFraudSignalType.TANK_SANITY_REPEAT)
        .all()
    )
    for signal in tank_sanity_signals:
        if signal.vehicle_id:
            vehicle_rollups[str(signal.vehicle_id)]["tank_sanity_exceeded_count"] += 1

    route_deviations = (
        db.query(LogisticsDeviationEvent, LogisticsOrder.driver_id)
        .join(LogisticsOrder, LogisticsOrder.id == LogisticsDeviationEvent.order_id)
        .filter(LogisticsDeviationEvent.ts >= start_at)
        .filter(LogisticsDeviationEvent.ts < end_at)
        .filter(LogisticsDeviationEvent.event_type == LogisticsDeviationEventType.OFF_ROUTE)
        .all()
    )
    for event, driver_id in route_deviations:
        if driver_id:
            driver_rollups[str(driver_id)]["route_deviation_count"] += 1

    burst_signals = (
        db.query(FuelFraudSignal)
        .filter(FuelFraudSignal.ts >= start_at)
        .filter(FuelFraudSignal.ts < end_at)
        .filter(FuelFraudSignal.signal_type == FuelFraudSignalType.MULTI_CARD_SAME_STATION_BURST)
        .all()
    )
    for signal in burst_signals:
        if signal.station_id:
            station_rollups[str(signal.station_id)]["burst_events_count"] += 1

    station_outliers = (
        db.query(StationReputationDaily)
        .filter(StationReputationDaily.day == day)
        .all()
    )
    for record in station_outliers:
        bucket = station_rollups[str(record.station_id)]
        bucket["outlier_score"] = int(record.outlier_score)

    vehicle_distances = (
        db.query(LogisticsRouteSnapshot, LogisticsOrder.vehicle_id)
        .join(LogisticsOrder, LogisticsOrder.id == LogisticsRouteSnapshot.order_id)
        .filter(LogisticsRouteSnapshot.created_at >= start_at)
        .filter(LogisticsRouteSnapshot.created_at < end_at)
        .all()
    )
    for snapshot, vehicle_id in vehicle_distances:
        if vehicle_id:
            vehicle_rollups[str(vehicle_id)]["distance_km_estimate"] = vehicle_rollups[str(vehicle_id)].get(
                "distance_km_estimate", 0.0
            ) + float(snapshot.distance_km)

    driver_daily: list[FIDriverDaily] = []
    for payload in driver_rollups.values():
        record = repository.upsert_driver_daily(
            db,
            {
                "tenant_id": payload["tenant_id"],
                "client_id": payload["client_id"],
                "driver_id": payload["driver_id"],
                "day": payload["day"],
                "fuel_tx_count": payload.get("fuel_tx_count", 0),
                "fuel_volume_ml": payload.get("fuel_volume_ml", 0),
                "fuel_amount_minor": payload.get("fuel_amount_minor", 0),
                "night_fuel_tx_count": payload.get("night_fuel_tx_count", 0),
                "off_route_fuel_count": payload.get("off_route_fuel_count", 0),
                "route_deviation_count": payload.get("route_deviation_count", 0),
                "review_required_count": payload.get("review_required_count", 0),
                "risk_block_count": payload.get("risk_block_count", 0),
            },
        )
        driver_daily.append(record)

    vehicle_daily: list[FIVehicleDaily] = []
    for payload in vehicle_rollups.values():
        distance = payload.get("distance_km_estimate")
        fuel_volume_ml = payload.get("fuel_volume_ml", 0)
        fuel_per_100km_ml = (fuel_volume_ml / distance) * 100 if distance else None
        record = repository.upsert_vehicle_daily(
            db,
            {
                "tenant_id": payload["tenant_id"],
                "client_id": payload["client_id"],
                "vehicle_id": payload["vehicle_id"],
                "day": payload["day"],
                "fuel_volume_ml": fuel_volume_ml,
                "fuel_amount_minor": payload.get("fuel_amount_minor", 0),
                "distance_km_estimate": distance,
                "fuel_per_100km_ml": fuel_per_100km_ml,
                "off_route_count": payload.get("off_route_count", 0),
                "tank_sanity_exceeded_count": payload.get("tank_sanity_exceeded_count", 0),
            },
        )
        vehicle_daily.append(record)

    station_daily: list[FIStationDaily] = []
    for payload in station_rollups.values():
        tx_count = payload.get("tx_count", 0)
        avg_volume = payload.get("volume_sum_ml", 0) / tx_count if tx_count else None
        avg_amount = payload.get("amount_sum_minor", 0) / tx_count if tx_count else None
        record = repository.upsert_station_daily(
            db,
            {
                "tenant_id": payload["tenant_id"],
                "network_id": payload.get("network_id"),
                "station_id": payload["station_id"],
                "day": payload["day"],
                "tx_count": tx_count,
                "distinct_cards_count": len(payload.get("card_ids", set())),
                "distinct_drivers_count": len(payload.get("driver_ids", set())),
                "avg_volume_ml": int(avg_volume) if avg_volume is not None else None,
                "avg_amount_minor": int(avg_amount) if avg_amount is not None else None,
                "risk_block_count": payload.get("risk_block_count", 0),
                "decline_count": payload.get("decline_count", 0),
                "burst_events_count": payload.get("burst_events_count", 0),
                "outlier_score": payload.get("outlier_score"),
            },
        )
        station_daily.append(record)

    return {
        "drivers": driver_daily,
        "vehicles": vehicle_daily,
        "stations": station_daily,
    }


__all__ = ["compute_daily_aggregates"]
