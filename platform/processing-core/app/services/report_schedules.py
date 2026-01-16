from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.report_schedules import ReportScheduleKind


class ReportScheduleValidationError(ValueError):
    pass


_DELIVERY_ROLE_MAP = {
    "OWNER": "CLIENT_OWNER",
    "ADMIN": "CLIENT_ADMIN",
    "CLIENT_OWNER": "CLIENT_OWNER",
    "CLIENT_ADMIN": "CLIENT_ADMIN",
}


def normalize_delivery_roles(roles: list[str]) -> list[str]:
    normalized: list[str] = []
    for role in roles or []:
        role_key = str(role).upper().strip()
        mapped = _DELIVERY_ROLE_MAP.get(role_key)
        if not mapped:
            raise ReportScheduleValidationError("invalid_delivery_role")
        normalized.append(mapped)
    return sorted(set(normalized))


def normalize_schedule_meta(kind: ReportScheduleKind, meta: dict[str, int]) -> dict[str, int]:
    if not isinstance(meta, dict):
        raise ReportScheduleValidationError("invalid_schedule_meta")
    hour = _parse_int(meta.get("hour"), "hour", min_value=0, max_value=23)
    minute = _parse_int(meta.get("minute"), "minute", min_value=0, max_value=59)

    if kind == ReportScheduleKind.DAILY:
        return {"hour": hour, "minute": minute}
    if kind == ReportScheduleKind.WEEKLY:
        weekday_raw = _parse_int(meta.get("weekday"), "weekday", min_value=0, max_value=7)
        weekday = weekday_raw - 1 if weekday_raw >= 1 else weekday_raw
        if weekday < 0 or weekday > 6:
            raise ReportScheduleValidationError("invalid_weekday")
        return {"weekday": weekday, "hour": hour, "minute": minute}
    if kind == ReportScheduleKind.MONTHLY:
        day_of_month = _parse_int(meta.get("day_of_month"), "day_of_month", min_value=1, max_value=31)
        return {"day_of_month": day_of_month, "hour": hour, "minute": minute}
    raise ReportScheduleValidationError("invalid_schedule_kind")


def compute_next_run_at(kind: ReportScheduleKind, meta: dict[str, int], tz_name: str) -> datetime:
    tzinfo = _resolve_timezone(tz_name)
    now = datetime.now(timezone.utc).astimezone(tzinfo)

    if kind == ReportScheduleKind.DAILY:
        candidate = _replace_time(now, meta["hour"], meta["minute"])
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    if kind == ReportScheduleKind.WEEKLY:
        candidate = _replace_time(now, meta["hour"], meta["minute"])
        target_weekday = meta["weekday"]
        delta_days = (target_weekday - candidate.weekday()) % 7
        if delta_days == 0 and candidate <= now:
            delta_days = 7
        candidate = candidate + timedelta(days=delta_days)
        return candidate.astimezone(timezone.utc)

    if kind == ReportScheduleKind.MONTHLY:
        candidate = _replace_time(now, meta["hour"], meta["minute"])
        day_of_month = meta["day_of_month"]
        candidate = _replace_day_of_month(candidate, day_of_month)
        if candidate <= now:
            next_month = _add_months(candidate, 1)
            candidate = _replace_day_of_month(next_month, day_of_month)
        return candidate.astimezone(timezone.utc)

    raise ReportScheduleValidationError("invalid_schedule_kind")


def _resolve_timezone(tz_name: str):
    try:
        return ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        return timezone.utc


def validate_timezone(tz_name: str) -> None:
    try:
        ZoneInfo(tz_name)
    except Exception as exc:  # noqa: BLE001
        raise ReportScheduleValidationError("invalid_timezone") from exc


def _replace_time(value: datetime, hour: int, minute: int) -> datetime:
    return value.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _replace_day_of_month(value: datetime, day: int) -> datetime:
    last_day = calendar.monthrange(value.year, value.month)[1]
    safe_day = min(day, last_day)
    return value.replace(day=safe_day)


def _add_months(value: datetime, months: int) -> datetime:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return value.replace(year=year, month=month, day=min(value.day, last_day))


def _parse_int(value: object, field: str, *, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ReportScheduleValidationError(f"invalid_{field}") from exc
    if parsed < min_value or parsed > max_value:
        raise ReportScheduleValidationError(f"invalid_{field}")
    return parsed


__all__ = [
    "ReportScheduleValidationError",
    "compute_next_run_at",
    "normalize_delivery_roles",
    "normalize_schedule_meta",
    "validate_timezone",
]
