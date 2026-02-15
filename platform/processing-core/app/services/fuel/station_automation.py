from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fuel import FuelStation, FuelStationHealthSource, FuelTransaction, FuelTransactionStatus, OpsStationEvent

SYSTEM_ACTOR = "system"


@dataclass(frozen=True)
class HealthPolicy:
    offline_after_minutes: int = 30
    degraded_decline_rate_threshold: float = 0.35
    degraded_min_volume_1h: int = 20


@dataclass(frozen=True)
class RiskPolicy:
    red_tags_24h_threshold: int = 5
    yellow_tags_24h_threshold: int = 2


def evaluate_station_health(db: Session, *, now: datetime | None = None, policy: HealthPolicy | None = None) -> dict[str, int]:
    current = now or datetime.now(timezone.utc)
    config = policy or HealthPolicy()
    changed = 0
    skipped_manual = 0

    stations = db.query(FuelStation).all()
    for station in stations:
        if not station.health_auto_enabled:
            continue

        if station.health_manual_lock and (station.health_manual_until is None or current < station.health_manual_until):
            skipped_manual += 1
            continue

        heartbeat_age = _heartbeat_age_minutes(station.last_heartbeat, current)
        tx_volume_1h, decline_rate_1h = _load_tx_metrics_1h(db, station_id=str(station.id), now=current)

        if heartbeat_age is None or heartbeat_age > config.offline_after_minutes:
            target_status = "OFFLINE"
        elif tx_volume_1h >= config.degraded_min_volume_1h and decline_rate_1h >= config.degraded_decline_rate_threshold:
            target_status = "DEGRADED"
        else:
            target_status = "ONLINE"

        previous = station.health_status
        if previous == target_status:
            continue

        station.health_status = target_status
        station.health_source = FuelStationHealthSource.SYSTEM.value
        station.health_updated_by = SYSTEM_ACTOR
        station.health_updated_at = current
        station.health_reason = (
            f"AUTO: heartbeat_age_minutes={heartbeat_age}, tx_volume_1h={tx_volume_1h}, "
            f"decline_rate_1h={decline_rate_1h:.4f}"
        )
        station.health_last_auto_at = current

        db.add(
            OpsStationEvent(
                station_id=station.id,
                event_type="HEALTH_CHANGED",
                old_value=previous,
                new_value=target_status,
                computed_metrics={
                    "heartbeat_age_minutes": heartbeat_age,
                    "tx_volume_1h": tx_volume_1h,
                    "decline_rate_1h": decline_rate_1h,
                },
                policy_snapshot={
                    "offline_after_minutes": config.offline_after_minutes,
                    "degraded_decline_rate_threshold": config.degraded_decline_rate_threshold,
                    "degraded_min_volume_1h": config.degraded_min_volume_1h,
                    "window_minutes": 60,
                },
                created_by=SYSTEM_ACTOR,
            )
        )
        changed += 1

    return {"changed": changed, "skipped_manual": skipped_manual}


def evaluate_station_risk(db: Session, *, now: datetime | None = None, policy: RiskPolicy | None = None) -> dict[str, int]:
    current = now or datetime.now(timezone.utc)
    config = policy or RiskPolicy()
    changed = 0
    skipped_manual = 0

    stations = db.query(FuelStation).all()
    for station in stations:
        if not station.risk_auto_enabled:
            continue

        if station.risk_manual_lock and (station.risk_manual_until is None or current < station.risk_manual_until):
            skipped_manual += 1
            continue

        red_24h, yellow_24h, volume_24h = _load_risk_counts_24h(db, station_id=str(station.id), now=current)

        if red_24h >= config.red_tags_24h_threshold:
            target_zone = "RED"
        elif yellow_24h >= config.yellow_tags_24h_threshold:
            target_zone = "YELLOW"
        else:
            target_zone = "GREEN"

        previous = station.risk_zone
        if previous == target_zone:
            continue

        station.risk_zone = target_zone
        station.risk_zone_reason = (
            f"AUTO: risk_red_24h={red_24h}, risk_yellow_24h={yellow_24h}, "
            f"policy red>={config.red_tags_24h_threshold}, yellow>={config.yellow_tags_24h_threshold}"
        )
        station.risk_zone_updated_by = SYSTEM_ACTOR
        station.risk_zone_updated_at = current
        station.risk_last_auto_at = current

        db.add(
            OpsStationEvent(
                station_id=station.id,
                event_type="RISK_CHANGED",
                old_value=previous,
                new_value=target_zone,
                computed_metrics={
                    "risk_red_count_24h": red_24h,
                    "risk_yellow_count_24h": yellow_24h,
                    "volume_24h": volume_24h,
                },
                policy_snapshot={
                    "red_tags_24h_threshold": config.red_tags_24h_threshold,
                    "yellow_tags_24h_threshold": config.yellow_tags_24h_threshold,
                    "window_hours": 24,
                },
                created_by=SYSTEM_ACTOR,
            )
        )
        changed += 1

    return {"changed": changed, "skipped_manual": skipped_manual}


def _heartbeat_age_minutes(last_heartbeat: datetime | None, now: datetime) -> int | None:
    if last_heartbeat is None:
        return None
    return max(0, int((now - _ensure_utc(last_heartbeat)).total_seconds() // 60))


def _load_tx_metrics_1h(db: Session, *, station_id: str, now: datetime) -> tuple[int, float]:
    window_start = now - timedelta(minutes=60)
    rows = (
        db.query(FuelTransaction.status, func.count(FuelTransaction.id))
        .filter(FuelTransaction.station_id == station_id)
        .filter(FuelTransaction.occurred_at >= window_start)
        .filter(FuelTransaction.occurred_at <= now)
        .group_by(FuelTransaction.status)
        .all()
    )

    captured = 0
    declined = 0
    for status, count in rows:
        if status in {FuelTransactionStatus.AUTHORIZED, FuelTransactionStatus.SETTLED}:
            captured += int(count or 0)
        elif status == FuelTransactionStatus.DECLINED:
            declined += int(count or 0)

    total = captured + declined
    decline_rate = float(declined / max(1, total))
    return total, decline_rate


def _load_risk_counts_24h(db: Session, *, station_id: str, now: datetime) -> tuple[int, int, int]:
    window_start = now - timedelta(hours=24)
    tx_rows = (
        db.query(FuelTransaction.meta)
        .filter(FuelTransaction.station_id == station_id)
        .filter(FuelTransaction.occurred_at >= window_start)
        .filter(FuelTransaction.occurred_at <= now)
        .all()
    )

    red = 0
    yellow = 0
    for (meta,) in tx_rows:
        tags = ((meta or {}).get("risk_tags") or []) if isinstance(meta, dict) else []
        if "STATION_RISK_RED" in tags:
            red += 1
        if "STATION_RISK_YELLOW" in tags:
            yellow += 1

    return red, yellow, len(tx_rows)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
