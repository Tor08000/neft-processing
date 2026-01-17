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


def compute_next_run_at(
    kind: ReportScheduleKind,
    meta: dict[str, int],
    tz_name: str,
    anchor_utc: datetime | None = None,
) -> datetime:
    tzinfo = _resolve_timezone(tz_name)
    anchor = anchor_utc or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    now_local = anchor.astimezone(tzinfo)

    candidate = _candidate_local(kind, meta, now_local, tzinfo)
    if candidate <= now_local:
        candidate = _advance_candidate(kind, meta, candidate)
    candidate = _resolve_local_datetime(candidate, tzinfo)
    return candidate.astimezone(timezone.utc)


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


def _candidate_local(
    kind: ReportScheduleKind,
    meta: dict[str, int],
    now_local: datetime,
    tzinfo: ZoneInfo,
) -> datetime:
    if kind == ReportScheduleKind.DAILY:
        return _build_local_datetime(now_local, meta["hour"], meta["minute"], tzinfo)
    if kind == ReportScheduleKind.WEEKLY:
        base = _build_local_datetime(now_local, meta["hour"], meta["minute"], tzinfo)
        target_weekday = meta["weekday"]
        delta_days = (target_weekday - base.weekday()) % 7
        return base + timedelta(days=delta_days)
    if kind == ReportScheduleKind.MONTHLY:
        base = _build_local_datetime(now_local, meta["hour"], meta["minute"], tzinfo)
        return _replace_day_of_month(base, meta["day_of_month"])
    raise ReportScheduleValidationError("invalid_schedule_kind")


def _advance_candidate(
    kind: ReportScheduleKind,
    meta: dict[str, int],
    candidate: datetime,
) -> datetime:
    if kind == ReportScheduleKind.DAILY:
        return candidate + timedelta(days=1)
    if kind == ReportScheduleKind.WEEKLY:
        return candidate + timedelta(days=7)
    if kind == ReportScheduleKind.MONTHLY:
        next_month = _add_months(candidate, 1)
        return _replace_day_of_month(next_month, meta["day_of_month"])
    raise ReportScheduleValidationError("invalid_schedule_kind")


def _build_local_datetime(now_local: datetime, hour: int, minute: int, tzinfo: ZoneInfo) -> datetime:
    return datetime(
        year=now_local.year,
        month=now_local.month,
        day=now_local.day,
        hour=hour,
        minute=minute,
        tzinfo=tzinfo,
    )


def _resolve_local_datetime(value: datetime, tzinfo: ZoneInfo) -> datetime:
    candidate = value.replace(tzinfo=tzinfo)
    fold_zero = candidate.replace(fold=0)
    fold_one = candidate.replace(fold=1)
    valid_zero = _is_valid_local_time(fold_zero, tzinfo)
    valid_one = _is_valid_local_time(fold_one, tzinfo)
    if valid_zero and valid_one:
        return fold_zero
    if valid_zero:
        return fold_zero
    if valid_one:
        return fold_one
    return _shift_to_next_valid_time(fold_zero, tzinfo)


def _is_valid_local_time(value: datetime, tzinfo: ZoneInfo) -> bool:
    roundtrip = value.astimezone(timezone.utc).astimezone(tzinfo)
    return roundtrip == value


def _shift_to_next_valid_time(value: datetime, tzinfo: ZoneInfo) -> datetime:
    shifted = value.astimezone(timezone.utc).astimezone(tzinfo)
    if shifted <= value:
        shifted = shifted + timedelta(hours=1)
        shifted = shifted.astimezone(timezone.utc).astimezone(tzinfo)
    return shifted


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
