from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.fuel import FuelLimit, FuelLimitPeriod, FuelLimitScopeType, FuelLimitType
from app.schemas.fuel import DeclineCode, LimitExplain
from app.services.fuel import repository

DEFAULT_TZ = "Europe/Moscow"


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    decline_code: DeclineCode | None
    explain: LimitExplain | None


def _period_bounds(period: FuelLimitPeriod, at: datetime, tz_name: str) -> tuple[datetime, datetime]:
    local = at.astimezone(ZoneInfo(tz_name))
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


def _window_active(limit: FuelLimit, at: datetime) -> bool:
    if limit.time_window_start is None or limit.time_window_end is None:
        return True
    tz_name = limit.timezone or DEFAULT_TZ
    local_time = at.astimezone(ZoneInfo(tz_name)).time()
    start = limit.time_window_start
    end = limit.time_window_end
    if start == end:
        return True
    if start < end:
        return start <= local_time <= end
    return local_time >= start or local_time <= end


def _matched_on(limit: FuelLimit) -> list[str]:
    matched = []
    if limit.fuel_type_code is not None:
        matched.append("fuel_type")
    if limit.station_id is not None:
        matched.append("station")
    if limit.station_network_id is not None:
        matched.append("station_network")
    if limit.time_window_start and limit.time_window_end:
        matched.append("time_window")
    return matched


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
    fuel_type,
    station_id: str | None,
    station_network_id: str | None,
) -> LimitDecision:
    selectors = [
        (FuelLimitScopeType.CARD, card_id, True, True),
        (FuelLimitScopeType.CARD, card_id, True, False),
        (FuelLimitScopeType.VEHICLE, vehicle_id, True, False),
        (FuelLimitScopeType.CARD, card_id, False, False),
        (FuelLimitScopeType.DRIVER, driver_id, False, False),
        (FuelLimitScopeType.CARD_GROUP, card_group_id, False, False),
        (FuelLimitScopeType.CLIENT, None, False, False),
    ]

    for scope_type, scope_id, require_fuel, require_station in selectors:
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
                fuel_type_code=fuel_type,
                station_id=station_id,
                station_network_id=station_network_id,
            )
        )
        for limit in limits:
            if require_fuel and limit.fuel_type_code is None:
                continue
            if require_station and limit.station_id is None:
                continue
            if require_fuel and not require_station and limit.station_network_id is None:
                continue
            if not _window_active(limit, at):
                explain = LimitExplain(
                    applied_limit_id=str(limit.id),
                    matched_on=_matched_on(limit),
                    scope_type=limit.scope_type,
                    scope_id=limit.scope_id,
                    limit_type=limit.limit_type,
                    period=limit.period,
                    limit=int(limit.value),
                    used=0,
                    attempt=0,
                    remaining=int(limit.value),
                    time_window_start=limit.time_window_start.isoformat() if limit.time_window_start else None,
                    time_window_end=limit.time_window_end.isoformat() if limit.time_window_end else None,
                    timezone=limit.timezone,
                )
                return LimitDecision(
                    allowed=False,
                    decline_code=DeclineCode.LIMIT_TIME_WINDOW,
                    explain=explain,
                )
            tz_name = limit.timezone or DEFAULT_TZ
            start_at, end_at = _period_bounds(limit.period, at, tz_name)
            used = repository.sum_fuel_usage(
                db,
                tenant_id=tenant_id,
                client_id=client_id,
                scope_type=limit.scope_type.value,
                scope_id=limit.scope_id,
                start_at=start_at,
                end_at=end_at,
                limit_type=limit.limit_type.value,
                fuel_type_code=limit.fuel_type_code,
                station_id=str(limit.station_id) if limit.station_id else None,
                station_network_id=str(limit.station_network_id) if limit.station_network_id else None,
            )
            attempt = amount_minor
            if limit.limit_type == FuelLimitType.VOLUME:
                attempt = volume_ml
            elif limit.limit_type == FuelLimitType.COUNT:
                attempt = 1
            if used + attempt > limit.value:
                remaining = max(0, limit.value - used)
                explain = LimitExplain(
                    applied_limit_id=str(limit.id),
                    matched_on=_matched_on(limit),
                    scope_type=limit.scope_type,
                    scope_id=limit.scope_id,
                    limit_type=limit.limit_type,
                    period=limit.period,
                    limit=int(limit.value),
                    used=int(used),
                    attempt=int(attempt),
                    remaining=int(remaining),
                    time_window_start=limit.time_window_start.isoformat() if limit.time_window_start else None,
                    time_window_end=limit.time_window_end.isoformat() if limit.time_window_end else None,
                    timezone=limit.timezone,
                )
                return LimitDecision(
                    allowed=False,
                    decline_code=DeclineCode.LIMIT_EXCEEDED,
                    explain=explain,
                )

    return LimitDecision(allowed=True, decline_code=None, explain=None)


__all__ = ["LimitDecision", "check_limits"]
