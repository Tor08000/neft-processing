from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func

from app.models.fleet import FleetDriver, FleetVehicle
from app.models.fuel import FuelCard, FuelStation, FuelTransaction, FuelTransactionStatus, FuelType
from app.schemas.fuel import DeclineCode
from app.services.decision import DecisionAction, DecisionContext
from app.services.fuel import repository
from app.services.logistics import repository as logistics_repository

MSK_TZ = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True)
class RiskContextResult:
    decision_context: DecisionContext
    decline_code: DeclineCode | None
    factors: list[str]


def build_risk_context_for_fuel_tx(
    *,
    tenant_id: int,
    client_id: str,
    card: FuelCard,
    station: FuelStation,
    vehicle: FleetVehicle | None,
    driver: FleetDriver | None,
    fuel_type: FuelType,
    amount_minor: int,
    volume_ml: int,
    occurred_at: datetime,
    currency: str,
    subject_id: str,
    policy_override_id: str | None,
    thresholds_override: dict | None,
    policy_source: str,
    logistics_window_hours: int | None,
    severity_multiplier: float | None,
    db,
) -> RiskContextResult:
    local_ts = occurred_at.astimezone(MSK_TZ)
    hour_of_day = local_ts.hour
    last_hour = occurred_at - timedelta(hours=1)
    last_day = occurred_at - timedelta(hours=24)

    tx_count_1h = repository.list_fuel_tx_count(db, card_id=str(card.id), start_at=last_hour, end_at=occurred_at)
    tx_count_24h = repository.list_fuel_tx_count(db, card_id=str(card.id), start_at=last_day, end_at=occurred_at)

    totals_24h = (
        db.query(
            func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0),
            func.coalesce(func.sum(FuelTransaction.volume_ml), 0),
        )
        .filter(FuelTransaction.card_id == card.id)
        .filter(
            FuelTransaction.status.in_(
                [
                    FuelTransactionStatus.AUTHORIZED,
                    FuelTransactionStatus.REVIEW_REQUIRED,
                    FuelTransactionStatus.SETTLED,
                ]
            )
        )
        .filter(FuelTransaction.occurred_at >= last_day)
        .filter(FuelTransaction.occurred_at <= occurred_at)
        .one()
    )
    total_amount_24h = int(totals_24h[0] or 0)
    total_volume_24h = int(totals_24h[1] or 0)

    totals_1h = (
        db.query(
            func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0),
        )
        .filter(FuelTransaction.card_id == card.id)
        .filter(
            FuelTransaction.status.in_(
                [
                    FuelTransactionStatus.AUTHORIZED,
                    FuelTransactionStatus.REVIEW_REQUIRED,
                    FuelTransactionStatus.SETTLED,
                ]
            )
        )
        .filter(FuelTransaction.occurred_at >= last_hour)
        .filter(FuelTransaction.occurred_at <= occurred_at)
        .one()
    )
    total_amount_1h = int(totals_1h[0] or 0)

    factors: list[str] = []
    decline_code: DeclineCode | None = None
    if vehicle and vehicle.tank_capacity_liters:
        capacity_ml = int(Decimal(vehicle.tank_capacity_liters) * Decimal("1000"))
        if volume_ml > int(capacity_ml * 1.2):
            factors.append("tank_sanity_exceeded")
            decline_code = DeclineCode.RISK_BLOCK
    if tx_count_1h >= 5 or tx_count_24h >= 20:
        factors.append("velocity_spike")
        decline_code = decline_code or DeclineCode.RISK_BLOCK

    logistics_signals = _summarize_logistics_signals(
        db,
        client_id=client_id,
        vehicle_id=str(vehicle.id) if vehicle else None,
        driver_id=str(driver.id) if driver else None,
        occurred_at=occurred_at,
        window_hours=logistics_window_hours,
        severity_multiplier=severity_multiplier,
    )
    metadata = {
        "card_status": card.status.value,
        "station_id": str(station.id),
        "network_id": str(station.network_id),
        "fuel_type": fuel_type.value,
        "volume_ml": volume_ml,
        "volume_liters": float(Decimal(volume_ml) / Decimal("1000")),
        "amount_total_minor": amount_minor,
        "tx_count_1h": int(tx_count_1h),
        "tx_count_24h": int(tx_count_24h),
        "amount_sum_1h": total_amount_1h,
        "amount_sum_24h": total_amount_24h,
        "total_amount_24h": total_amount_24h,
        "total_volume_24h": total_volume_24h,
        "hour_of_day": hour_of_day,
        "vehicle_id": str(vehicle.id) if vehicle else None,
        "driver_id": str(driver.id) if driver else None,
        "factors": factors,
        "subject_id": subject_id,
        "policy_override_id": policy_override_id,
        "thresholds_override": thresholds_override,
        "policy_source": policy_source,
        "logistics_signals": logistics_signals,
        "logistics_off_route_summary": _summarize_off_route_events(
            db,
            order_id=logistics_signals.get("order_id"),
            occurred_at=occurred_at,
            window_hours=logistics_window_hours,
        ),
    }
    decision_context = DecisionContext(
        tenant_id=tenant_id,
        client_id=client_id,
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=amount_minor,
        currency=currency,
        payment_method="FUEL_CARD",
        history={},
        metadata=metadata,
    )

    return RiskContextResult(decision_context=decision_context, decline_code=decline_code, factors=factors)


def _summarize_logistics_signals(
    db,
    *,
    client_id: str,
    vehicle_id: str | None,
    driver_id: str | None,
    occurred_at: datetime,
    window_hours: int | None,
    severity_multiplier: float | None,
) -> dict:
    window = window_hours or 24
    multiplier = severity_multiplier or 1.0
    since = occurred_at - timedelta(hours=window)
    signals = logistics_repository.list_recent_risk_signals(
        db,
        client_id=client_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        since=since,
    )
    summary: dict[str, dict] = {"order_id": None}
    for signal in signals:
        summary["order_id"] = str(signal.order_id)
        entry = summary.setdefault(
            signal.signal_type.value,
            {"count": 0, "max_severity": 0, "latest_ts": None},
        )
        entry["count"] += 1
        adjusted_severity = float(signal.severity) * multiplier
        entry["max_severity"] = max(entry["max_severity"], adjusted_severity)
        if entry["latest_ts"] is None or signal.ts > entry["latest_ts"]:
            entry["latest_ts"] = signal.ts.isoformat()
    return summary


def _summarize_off_route_events(
    db,
    *,
    order_id: str | None,
    occurred_at: datetime,
    window_hours: int | None,
) -> dict | None:
    if not order_id:
        return None
    window = window_hours or 24
    since = occurred_at - timedelta(hours=window)
    events = logistics_repository.list_recent_deviation_events(db, order_id=order_id, since=since)
    off_route = [event for event in events if event.event_type.value == "OFF_ROUTE"]
    if not off_route:
        return {"count": 0, "max_severity": 0, "last_ts": None}
    max_severity = max(
        {"LOW": 30, "MEDIUM": 60, "HIGH": 80}.get(event.severity.value, 0) for event in off_route
    )
    last_ts = max(event.ts for event in off_route).isoformat()
    return {"count": len(off_route), "max_severity": max_severity, "last_ts": last_ts}
