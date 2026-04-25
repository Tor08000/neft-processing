from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    applied_limits: list[LimitExplain]
    warnings: list[str]


@dataclass(frozen=True)
class LimitResolution:
    applied_limits: list[LimitExplain]
    blocking_limit: LimitExplain | None
    blocking_code: DeclineCode | None
    warnings: list[str]


def _period_bounds(period: FuelLimitPeriod, at: datetime, tz_name: str) -> tuple[datetime, datetime]:
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    local = at.astimezone(ZoneInfo(tz_name))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == FuelLimitPeriod.DAILY:
        return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)
    if period == FuelLimitPeriod.WEEKLY:
        week_start = start - timedelta(days=start.weekday())
        return week_start.astimezone(timezone.utc), (week_start + timedelta(days=7)).astimezone(timezone.utc)
    month_start = start.replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)
    return month_start.astimezone(timezone.utc), month_end.astimezone(timezone.utc)


_SCOPE_PRIORITY = {
    FuelLimitScopeType.CARD: 0,
    FuelLimitScopeType.DRIVER: 1,
    FuelLimitScopeType.VEHICLE: 2,
    FuelLimitScopeType.CARD_GROUP: 3,
    FuelLimitScopeType.CLIENT: 4,
}

_PERIOD_PRIORITY = {
    FuelLimitPeriod.DAILY: 0,
    FuelLimitPeriod.WEEKLY: 1,
    FuelLimitPeriod.MONTHLY: 2,
}

_LIMIT_TYPE_PRIORITY = {
    FuelLimitType.COUNT: 0,
    FuelLimitType.VOLUME: 1,
    FuelLimitType.AMOUNT: 2,
}


def _specificity_rank(limit: FuelLimit) -> int:
    if limit.fuel_type_code is not None and limit.station_id is not None:
        return 0
    if limit.fuel_type_code is not None and limit.station_network_id is not None:
        return 1
    if limit.fuel_type_code is not None:
        return 2
    if limit.station_id is not None or limit.station_network_id is not None:
        return 3
    return 4


def _sorted_limits(limits: list[FuelLimit]) -> list[FuelLimit]:
    return sorted(
        limits,
        key=lambda item: (
            _SCOPE_PRIORITY.get(item.scope_type, 99),
            _specificity_rank(item),
            _PERIOD_PRIORITY.get(item.period, 99),
            _LIMIT_TYPE_PRIORITY.get(item.limit_type, 99),
            item.priority,
            item.value,
        ),
    )


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


def _attempt_value(limit: FuelLimit, *, amount_minor: int, volume_ml: int) -> int:
    if limit.limit_type == FuelLimitType.VOLUME:
        return volume_ml
    if limit.limit_type == FuelLimitType.COUNT:
        return 1
    return amount_minor


def _limit_decline_code(limit: FuelLimit) -> DeclineCode:
    if limit.limit_type == FuelLimitType.COUNT:
        return DeclineCode.LIMIT_EXCEEDED_COUNT
    if limit.limit_type == FuelLimitType.VOLUME:
        return DeclineCode.LIMIT_EXCEEDED_VOLUME
    return DeclineCode.LIMIT_EXCEEDED_AMOUNT


def resolve_applicable_limits(
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
) -> LimitResolution:
    selectors = [
        (FuelLimitScopeType.CARD, card_id),
        (FuelLimitScopeType.DRIVER, driver_id),
        (FuelLimitScopeType.VEHICLE, vehicle_id),
        (FuelLimitScopeType.CARD_GROUP, card_group_id),
        (FuelLimitScopeType.CLIENT, None),
    ]
    warnings: list[str] = []
    collected: list[FuelLimit] = []
    for scope_type, scope_id in selectors:
        if scope_type != FuelLimitScopeType.CLIENT and not scope_id:
            continue
        collected.extend(
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

    applied_limits: list[LimitExplain] = []
    blocking_limit: LimitExplain | None = None
    blocking_code: DeclineCode | None = None
    for limit in _sorted_limits(collected):
        attempt = _attempt_value(limit, amount_minor=amount_minor, volume_ml=volume_ml)
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
                attempt=int(attempt),
                remaining=int(limit.value),
                time_window_start=limit.time_window_start.isoformat() if limit.time_window_start else None,
                time_window_end=limit.time_window_end.isoformat() if limit.time_window_end else None,
                timezone=limit.timezone,
            )
            applied_limits.append(explain)
            if blocking_limit is None:
                blocking_limit = explain
                blocking_code = DeclineCode.LIMIT_TIME_WINDOW
            continue

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
        remaining = max(0, int(limit.value) - int(used))
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
        applied_limits.append(explain)
        if blocking_limit is None and used + attempt > limit.value:
            blocking_limit = explain
            blocking_code = _limit_decline_code(limit)

    return LimitResolution(
        applied_limits=applied_limits,
        blocking_limit=blocking_limit,
        blocking_code=blocking_code,
        warnings=warnings,
    )


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
    resolution = resolve_applicable_limits(
        db=db,
        tenant_id=tenant_id,
        client_id=client_id,
        card_id=card_id,
        card_group_id=card_group_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        at=at,
        amount_minor=amount_minor,
        volume_ml=volume_ml,
        currency=currency,
        fuel_type=fuel_type,
        station_id=station_id,
        station_network_id=station_network_id,
    )

    if resolution.blocking_limit:
        return LimitDecision(
            allowed=False,
            decline_code=resolution.blocking_code,
            explain=resolution.blocking_limit,
            applied_limits=resolution.applied_limits,
            warnings=resolution.warnings,
        )

    return LimitDecision(
        allowed=True,
        decline_code=None,
        explain=None,
        applied_limits=resolution.applied_limits,
        warnings=resolution.warnings,
    )


__all__ = ["LimitDecision", "LimitResolution", "check_limits", "resolve_applicable_limits"]
