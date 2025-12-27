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
    db,
) -> RiskContextResult:
    local_ts = occurred_at.astimezone(MSK_TZ)
    hour_of_day = local_ts.hour
    last_hour = occurred_at - timedelta(hours=1)
    last_day = occurred_at - timedelta(hours=24)

    tx_count_1h = repository.list_fuel_tx_count(db, card_id=str(card.id), start_at=last_hour, end_at=occurred_at)
    tx_count_24h = repository.list_fuel_tx_count(db, card_id=str(card.id), start_at=last_day, end_at=occurred_at)

    totals = (
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
    total_amount_24h = int(totals[0] or 0)
    total_volume_24h = int(totals[1] or 0)

    factors: list[str] = []
    decline_code: DeclineCode | None = None
    if vehicle and vehicle.tank_capacity_liters:
        capacity_ml = int(Decimal(vehicle.tank_capacity_liters) * Decimal("1000"))
        if volume_ml > int(capacity_ml * 1.2):
            factors.append("tank_sanity_exceeded")
            decline_code = DeclineCode.TANK_SANITY_EXCEEDED
    if tx_count_1h >= 5 or tx_count_24h >= 20:
        factors.append("velocity_spike")
        decline_code = decline_code or DeclineCode.VELOCITY_SPIKE

    metadata = {
        "card_status": card.status.value,
        "station_id": str(station.id),
        "network_id": str(station.network_id),
        "fuel_type": fuel_type.value,
        "volume_ml": volume_ml,
        "amount_total_minor": amount_minor,
        "tx_count_1h": int(tx_count_1h),
        "tx_count_24h": int(tx_count_24h),
        "total_amount_24h": total_amount_24h,
        "total_volume_24h": total_volume_24h,
        "hour_of_day": hour_of_day,
        "vehicle_id": str(vehicle.id) if vehicle else None,
        "driver_id": str(driver.id) if driver else None,
        "factors": factors,
        "subject_id": subject_id,
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
