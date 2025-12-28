from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.crm import CRMSubscription, CRMUsageCounter, CRMUsageMetric
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelTransaction, FuelTransactionStatus
from app.models.logistics import LogisticsOrder


@dataclass(frozen=True)
class UsageResult:
    counters: list[CRMUsageCounter]


def collect_usage(
    db: Session,
    *,
    subscription: CRMSubscription,
    billing_period_id: str,
    period_start: datetime,
    period_end: datetime,
    included: dict[str, int | None] | None = None,
) -> UsageResult:
    included = included or {}
    counters: list[CRMUsageCounter] = []

    cards_count = (
        db.query(FuelCard)
        .filter(FuelCard.client_id == subscription.client_id)
        .filter(FuelCard.status == FuelCardStatus.ACTIVE)
        .filter(FuelCard.created_at <= period_end)
        .count()
    )
    counters.append(
        CRMUsageCounter(
            subscription_id=subscription.id,
            billing_period_id=billing_period_id,
            metric=CRMUsageMetric.CARDS_COUNT,
            value=cards_count,
            limit_value=included.get("cards"),
        )
    )

    vehicles_count = (
        db.query(FleetVehicle)
        .filter(FleetVehicle.client_id == subscription.client_id)
        .filter(FleetVehicle.status == FleetVehicleStatus.ACTIVE)
        .filter(FleetVehicle.created_at <= period_end)
        .count()
    )
    counters.append(
        CRMUsageCounter(
            subscription_id=subscription.id,
            billing_period_id=billing_period_id,
            metric=CRMUsageMetric.VEHICLES_COUNT,
            value=vehicles_count,
            limit_value=included.get("vehicles"),
        )
    )

    drivers_count = (
        db.query(FleetDriver)
        .filter(FleetDriver.client_id == subscription.client_id)
        .filter(FleetDriver.status == FleetDriverStatus.ACTIVE)
        .filter(FleetDriver.created_at <= period_end)
        .count()
    )
    counters.append(
        CRMUsageCounter(
            subscription_id=subscription.id,
            billing_period_id=billing_period_id,
            metric=CRMUsageMetric.DRIVERS_COUNT,
            value=drivers_count,
            limit_value=included.get("drivers"),
        )
    )

    fuel_counts = (
        db.query(
            func.count(FuelTransaction.id),
            func.coalesce(func.sum(FuelTransaction.volume_ml), 0),
        )
        .filter(FuelTransaction.client_id == subscription.client_id)
        .filter(FuelTransaction.occurred_at >= period_start)
        .filter(FuelTransaction.occurred_at <= period_end)
        .filter(FuelTransaction.status == FuelTransactionStatus.SETTLED)
        .one()
    )
    fuel_tx_count = int(fuel_counts[0] or 0)
    fuel_volume = int(fuel_counts[1] or 0)
    counters.append(
        CRMUsageCounter(
            subscription_id=subscription.id,
            billing_period_id=billing_period_id,
            metric=CRMUsageMetric.FUEL_TX_COUNT,
            value=fuel_tx_count,
            limit_value=included.get("fuel_tx"),
        )
    )
    counters.append(
        CRMUsageCounter(
            subscription_id=subscription.id,
            billing_period_id=billing_period_id,
            metric=CRMUsageMetric.FUEL_VOLUME,
            value=fuel_volume,
            limit_value=included.get("fuel_volume"),
        )
    )

    logistics_orders = (
        db.query(LogisticsOrder)
        .filter(LogisticsOrder.client_id == subscription.client_id)
        .filter(
            (LogisticsOrder.created_at.between(period_start, period_end))
            | (LogisticsOrder.actual_end_at.between(period_start, period_end))
        )
        .count()
    )
    counters.append(
        CRMUsageCounter(
            subscription_id=subscription.id,
            billing_period_id=billing_period_id,
            metric=CRMUsageMetric.LOGISTICS_ORDERS,
            value=logistics_orders,
            limit_value=included.get("logistics_orders"),
        )
    )

    return UsageResult(counters=counters)


__all__ = ["UsageResult", "collect_usage"]
