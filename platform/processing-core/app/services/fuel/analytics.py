from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.models.fuel import (
    FuelAnomalyEvent,
    FuelAnalyticsEvent,
    FuelMisuseSignal,
    FuelStationOutlier,
    FuelTransaction,
)
from app.services.fuel import repository

MSK_TZ = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True)
class AnalyticsResult:
    anomaly_events: list[FuelAnomalyEvent]
    analytics_events: list[FuelAnalyticsEvent]
    misuse_signals: list[FuelMisuseSignal]
    station_outliers: list[FuelStationOutlier]


def evaluate_transaction(
    *,
    db,
    transaction: FuelTransaction,
    vehicle,
    station,
) -> AnalyticsResult:
    now = transaction.occurred_at
    start_30d = now - timedelta(days=30)
    start_24h = now - timedelta(hours=24)
    start_1h = now - timedelta(hours=1)

    anomalies: list[FuelAnomalyEvent] = []
    analytics_events: list[FuelAnalyticsEvent] = []
    misuse_signals: list[FuelMisuseSignal] = []
    station_outliers: list[FuelStationOutlier] = []

    avg_volume = repository.avg_card_volume_30d(db, card_id=str(transaction.card_id), start_at=start_30d, end_at=now)
    if avg_volume > 0 and transaction.volume_ml > int(avg_volume * 2.5):
        anomalies.append(
            FuelAnomalyEvent(
                fuel_tx_id=transaction.id,
                event_type="sudden_spike",
                severity="HIGH",
                explain={"avg_volume_ml": int(avg_volume), "current_volume_ml": transaction.volume_ml},
            )
        )
        analytics_events.append(
            FuelAnalyticsEvent(
                fuel_tx_id=transaction.id,
                signal_type="VELOCITY_SPIKE",
                severity="HIGH",
                explain={"avg_volume_ml": int(avg_volume), "current_volume_ml": transaction.volume_ml},
            )
        )

    tx_count_24h = repository.list_fuel_tx_count(
        db, card_id=str(transaction.card_id), start_at=start_24h, end_at=now
    )
    tx_count_30d = repository.list_fuel_tx_count(
        db, card_id=str(transaction.card_id), start_at=start_30d, end_at=now
    )
    avg_daily = tx_count_30d / 30 if tx_count_30d else 0
    if avg_daily and tx_count_24h > avg_daily * 3:
        anomalies.append(
            FuelAnomalyEvent(
                fuel_tx_id=transaction.id,
                event_type="frequency_spike",
                severity="MEDIUM",
                explain={"avg_daily": avg_daily, "count_24h": tx_count_24h},
            )
        )
        analytics_events.append(
            FuelAnalyticsEvent(
                fuel_tx_id=transaction.id,
                signal_type="VELOCITY_SPIKE",
                severity="MEDIUM",
                explain={"avg_daily": avg_daily, "count_24h": tx_count_24h},
            )
        )

    if vehicle and vehicle.tank_capacity_liters:
        capacity_ml = int(Decimal(vehicle.tank_capacity_liters) * Decimal("1000"))
        if transaction.volume_ml > capacity_ml:
            anomalies.append(
                FuelAnomalyEvent(
                    fuel_tx_id=transaction.id,
                    event_type="tank_capacity_exceeded",
                    severity="HIGH",
                    explain={"capacity_ml": capacity_ml, "volume_ml": transaction.volume_ml},
                )
            )
            analytics_events.append(
                FuelAnalyticsEvent(
                    fuel_tx_id=transaction.id,
                    signal_type="TANK_SANITY_EXCEEDED",
                    severity="HIGH",
                    explain={"capacity_ml": capacity_ml, "volume_ml": transaction.volume_ml},
                )
            )

    local_time = now.astimezone(MSK_TZ)
    if local_time.hour >= 23 or local_time.hour < 6:
        misuse_signals.append(
            FuelMisuseSignal(
                fuel_tx_id=transaction.id,
                signal="night_refuel",
                explain={"hour": local_time.hour},
            )
        )
        analytics_events.append(
            FuelAnalyticsEvent(
                fuel_tx_id=transaction.id,
                signal_type="VEHICLE_MISUSE_SUSPECTED",
                severity="MEDIUM",
                explain={"signal": "night_refuel", "hour": local_time.hour},
            )
        )

    driver_ids = repository.list_recent_card_driver_ids(
        db, card_id=str(transaction.card_id), start_at=start_1h, end_at=now
    )
    if transaction.driver_id and len(set(driver_ids)) > 1:
        misuse_signals.append(
            FuelMisuseSignal(
                fuel_tx_id=transaction.id,
                signal="multi_driver_short_window",
                explain={"drivers": driver_ids},
            )
        )
        analytics_events.append(
            FuelAnalyticsEvent(
                fuel_tx_id=transaction.id,
                signal_type="VEHICLE_MISUSE_SUSPECTED",
                severity="HIGH",
                explain={"signal": "multi_driver_short_window", "drivers": driver_ids},
            )
        )

    if station:
        station_avg, network_avg = repository.station_price_avg(
            db, station_id=str(station.id), network_id=str(station.network_id), start_at=start_30d, end_at=now
        )
        if network_avg and station_avg:
            if station_avg > network_avg * 1.3 or station_avg < network_avg * 0.7:
                station_outliers.append(
                    FuelStationOutlier(
                        station_id=station.id,
                        metric="avg_price_outlier",
                        value=int(station_avg),
                        baseline=int(network_avg),
                        explain={"station_avg": station_avg, "network_avg": network_avg},
                    )
                )
                analytics_events.append(
                    FuelAnalyticsEvent(
                        fuel_tx_id=transaction.id,
                        signal_type="STATION_OUTLIER_PRICE",
                        severity="MEDIUM",
                        explain={"station_avg": station_avg, "network_avg": network_avg},
                    )
                )

    return AnalyticsResult(
        anomaly_events=anomalies,
        analytics_events=analytics_events,
        misuse_signals=misuse_signals,
        station_outliers=station_outliers,
    )


def persist_results(db, result: AnalyticsResult) -> None:
    for event in result.anomaly_events:
        repository.add_anomaly_event(db, event)
    for event in result.analytics_events:
        repository.add_analytics_event(db, event)
    for signal in result.misuse_signals:
        repository.add_misuse_signal(db, signal)
    for outlier in result.station_outliers:
        repository.add_station_outlier(db, outlier)


__all__ = ["AnalyticsResult", "evaluate_transaction", "persist_results"]
