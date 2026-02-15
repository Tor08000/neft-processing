from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

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
    red_downgrade_streak_days: int = 3
    yellow_downgrade_streak_days: int = 7


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
    return evaluate_station_risk_escalation(db, now=now, policy=policy)


def evaluate_station_risk_escalation(
    db: Session,
    *,
    now: datetime | None = None,
    policy: RiskPolicy | None = None,
) -> dict[str, int]:
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
        previous = station.risk_zone

        if red_24h >= config.red_tags_24h_threshold:
            target_zone = "RED"
        elif yellow_24h >= config.yellow_tags_24h_threshold and previous in (None, "", "GREEN"):
            target_zone = "YELLOW"
        else:
            continue

        if previous == target_zone:
            continue

        _apply_risk_zone_change(
            db,
            station=station,
            previous=previous,
            target=target_zone,
            now=current,
            config=config,
            red_24h=red_24h,
            yellow_24h=yellow_24h,
            volume_24h=volume_24h,
            red_today=None,
            yellow_today=None,
        )
        changed += 1

    return {"changed": changed, "skipped_manual": skipped_manual}


def evaluate_station_risk_downgrade_daily(
    db: Session,
    *,
    now: datetime | None = None,
    policy: RiskPolicy | None = None,
) -> dict[str, int]:
    current = now or datetime.now(timezone.utc)
    today = current.date()
    config = policy or RiskPolicy()
    changed = 0
    skipped_manual = 0
    skipped_already_evaluated = 0
    streak_updated = 0

    stations = db.query(FuelStation).all()
    for station in stations:
        if not station.risk_auto_enabled:
            continue

        if station.risk_manual_lock and (station.risk_manual_until is None or current < station.risk_manual_until):
            skipped_manual += 1
            continue

        if station.risk_last_eval_day == today:
            skipped_already_evaluated += 1
            continue

        red_today, yellow_today = _load_risk_counts_for_day(db, station_id=str(station.id), day=today)

        if red_today:
            station.risk_red_clear_streak_days = 0
        else:
            station.risk_red_clear_streak_days = int(station.risk_red_clear_streak_days or 0) + 1

        if yellow_today or red_today:
            station.risk_yellow_clear_streak_days = 0
        else:
            station.risk_yellow_clear_streak_days = int(station.risk_yellow_clear_streak_days or 0) + 1

        station.risk_last_eval_day = today
        station.risk_last_auto_at = current
        streak_updated += 1

        previous = station.risk_zone
        target_zone = previous
        if previous == "RED" and station.risk_red_clear_streak_days >= config.red_downgrade_streak_days:
            target_zone = "YELLOW"
        elif previous == "YELLOW" and station.risk_yellow_clear_streak_days >= config.yellow_downgrade_streak_days:
            target_zone = "GREEN"

        if target_zone != previous:
            red_24h, yellow_24h, volume_24h = _load_risk_counts_24h(db, station_id=str(station.id), now=current)
            _apply_risk_zone_change(
                db,
                station=station,
                previous=previous,
                target=target_zone,
                now=current,
                config=config,
                red_24h=red_24h,
                yellow_24h=yellow_24h,
                volume_24h=volume_24h,
                red_today=red_today,
                yellow_today=yellow_today,
            )
            changed += 1

    return {
        "changed": changed,
        "skipped_manual": skipped_manual,
        "skipped_already_evaluated": skipped_already_evaluated,
        "streak_updated": streak_updated,
    }


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


def _load_risk_counts_for_day(db: Session, *, station_id: str, day: date) -> tuple[bool, bool]:
    day_start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    tx_rows = (
        db.query(FuelTransaction.meta)
        .filter(FuelTransaction.station_id == station_id)
        .filter(FuelTransaction.occurred_at >= day_start)
        .filter(FuelTransaction.occurred_at < day_end)
        .all()
    )

    red_today = False
    yellow_today = False
    for (meta,) in tx_rows:
        tags = ((meta or {}).get("risk_tags") or []) if isinstance(meta, dict) else []
        if "STATION_RISK_RED" in tags:
            red_today = True
        if "STATION_RISK_YELLOW" in tags:
            yellow_today = True
        if red_today and yellow_today:
            break

    return red_today, yellow_today


def _apply_risk_zone_change(
    db: Session,
    *,
    station: FuelStation,
    previous: str | None,
    target: str,
    now: datetime,
    config: RiskPolicy,
    red_24h: int,
    yellow_24h: int,
    volume_24h: int,
    red_today: bool | None,
    yellow_today: bool | None,
) -> None:
    station.risk_zone = target
    station.risk_zone_reason = (
        f"AUTO: risk_red_24h={red_24h}, risk_yellow_24h={yellow_24h}, "
        f"policy red>={config.red_tags_24h_threshold}, yellow>={config.yellow_tags_24h_threshold}, "
        f"downgrade red_clear>={config.red_downgrade_streak_days}, "
        f"yellow_clear>={config.yellow_downgrade_streak_days}"
    )
    station.risk_zone_updated_by = SYSTEM_ACTOR
    station.risk_zone_updated_at = now
    station.risk_last_auto_at = now

    db.add(
        OpsStationEvent(
            station_id=station.id,
            event_type="RISK_CHANGED",
            old_value=previous,
            new_value=target,
            computed_metrics={
                "risk_red_count_24h": red_24h,
                "risk_yellow_count_24h": yellow_24h,
                "volume_24h": volume_24h,
                "red_today": red_today,
                "yellow_today": yellow_today,
                "red_clear_streak_days": station.risk_red_clear_streak_days,
                "yellow_clear_streak_days": station.risk_yellow_clear_streak_days,
            },
            policy_snapshot={
                "offline_after_minutes": 30,
                "red_tags_24h_threshold": config.red_tags_24h_threshold,
                "yellow_tags_24h_threshold": config.yellow_tags_24h_threshold,
                "red_downgrade_streak_days": config.red_downgrade_streak_days,
                "yellow_downgrade_streak_days": config.yellow_downgrade_streak_days,
                "window_hours": 24,
            },
            created_by=SYSTEM_ACTOR,
        )
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
