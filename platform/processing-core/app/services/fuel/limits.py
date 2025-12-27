from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.fuel import FuelLimitPeriod, FuelLimitScopeType, FuelLimitType
from app.schemas.fuel import DeclineCode, LimitExplain
from app.services.fuel import repository

MSK_TZ = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    decline_code: DeclineCode | None
    explain: LimitExplain | None


def _period_bounds(period: FuelLimitPeriod, at: datetime) -> tuple[datetime, datetime]:
    local = at.astimezone(MSK_TZ)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == FuelLimitPeriod.DAILY:
        return start, start + timedelta(days=1)
    if period == FuelLimitPeriod.WEEKLY:
        week_start = start - timedelta(days=start.weekday())
        return week_start, week_start + timedelta(days=7)
    month_start = start.replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)
    return month_start, month_end


def _sorted_limits(limits):
    return sorted(limits, key=lambda item: (item.priority, item.value))


def check_limits(
    *,
    db,
    tenant_id: int,
    client_id: str,
    card_id: str,
    card_group_id: str | None,
    vehicle_id: str | None,
    driver_id: str | None,
    at: datetime,
    amount_minor: int,
    volume_ml: int,
    currency: str,
) -> LimitDecision:
    scope_order = [
        (FuelLimitScopeType.CARD, card_id),
        (FuelLimitScopeType.VEHICLE, vehicle_id),
        (FuelLimitScopeType.DRIVER, driver_id),
        (FuelLimitScopeType.CARD_GROUP, card_group_id),
        (FuelLimitScopeType.CLIENT, None),
    ]

    for scope_type, scope_id in scope_order:
        if scope_type != FuelLimitScopeType.CLIENT and not scope_id:
            continue
        limits = _sorted_limits(
            repository.list_active_limits(
                db,
                tenant_id=tenant_id,
                client_id=client_id,
                scope_type=scope_type,
                scope_id=scope_id,
                at=at,
                currency=currency,
            )
        )
        for limit in limits:
            start_at, end_at = _period_bounds(limit.period, at)
            used = repository.sum_fuel_usage(
                db,
                tenant_id=tenant_id,
                client_id=client_id,
                scope_type=limit.scope_type.value,
                scope_id=limit.scope_id,
                start_at=start_at,
                end_at=end_at,
                limit_type=limit.limit_type.value,
            )
            attempt = amount_minor
            decline_code = DeclineCode.LIMIT_EXCEEDED_AMOUNT
            if limit.limit_type == FuelLimitType.VOLUME:
                attempt = volume_ml
                decline_code = DeclineCode.LIMIT_EXCEEDED_VOLUME
            elif limit.limit_type == FuelLimitType.COUNT:
                attempt = 1
                decline_code = DeclineCode.LIMIT_EXCEEDED_COUNT
            if used + attempt > limit.value:
                remaining = max(0, limit.value - used)
                explain = LimitExplain(
                    scope_type=limit.scope_type,
                    scope_id=limit.scope_id,
                    limit_type=limit.limit_type,
                    period=limit.period,
                    limit=int(limit.value),
                    used=int(used),
                    attempt=int(attempt),
                    remaining=int(remaining),
                )
                return LimitDecision(
                    allowed=False,
                    decline_code=decline_code,
                    explain=explain,
                )

    return LimitDecision(allowed=True, decline_code=None, explain=None)


__all__ = ["LimitDecision", "check_limits"]
