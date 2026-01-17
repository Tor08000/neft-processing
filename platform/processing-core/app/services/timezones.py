from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.crm import CRMClient
from app.models.fleet import ClientEmployee
from app.models.report_schedules import ReportSchedule


DEFAULT_TIMEZONE = "UTC"


def validate_timezone_name(value: str) -> None:
    try:
        ZoneInfo(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("invalid_timezone") from exc


def _normalize_timezone(value: str | None) -> str | None:
    if not value:
        return None
    try:
        ZoneInfo(value)
        return value
    except Exception:  # noqa: BLE001
        return None


def resolve_user_timezone(
    db: Session,
    *,
    token: dict | None = None,
    user: ClientEmployee | None = None,
    org: CRMClient | None = None,
    schedule: ReportSchedule | None = None,
) -> str:
    user_timezone = _normalize_timezone(user.timezone) if user else None
    if not user_timezone and token:
        user_id = token.get("user_id") or token.get("sub")
        org_id = token.get("client_id")
        if user_id and org_id:
            employee = (
                db.query(ClientEmployee)
                .filter(ClientEmployee.id == str(user_id), ClientEmployee.client_id == str(org_id))
                .one_or_none()
            )
            if employee and employee.timezone:
                user_timezone = _normalize_timezone(employee.timezone)

    schedule_timezone = _normalize_timezone(schedule.timezone) if schedule else None
    org_timezone = _normalize_timezone(org.timezone) if org else None
    if not org_timezone:
        org_id = None
        if token and token.get("client_id"):
            org_id = token.get("client_id")
        elif schedule is not None:
            org_id = str(schedule.org_id)
        if org_id:
            crm_client = db.query(CRMClient).filter(CRMClient.id == str(org_id)).one_or_none()
            if crm_client and crm_client.timezone:
                org_timezone = _normalize_timezone(crm_client.timezone)

    return user_timezone or schedule_timezone or org_timezone or DEFAULT_TIMEZONE


def resolve_user_timezone_info(
    db: Session,
    *,
    token: dict | None = None,
    user: ClientEmployee | None = None,
    org: CRMClient | None = None,
    schedule: ReportSchedule | None = None,
) -> ZoneInfo:
    tz_name = resolve_user_timezone(db, token=token, user=user, org=org, schedule=schedule)
    try:
        return ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        return ZoneInfo(DEFAULT_TIMEZONE)


def format_datetime_for_user(
    db: Session,
    *,
    value: datetime | None,
    token: dict | None = None,
    user: ClientEmployee | None = None,
    org: CRMClient | None = None,
    schedule: ReportSchedule | None = None,
    fmt: str = "%d.%m.%Y %H:%M",
) -> tuple[str, str]:
    tz_name = resolve_user_timezone(db, token=token, user=user, org=org, schedule=schedule)
    try:
        tzinfo = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tzinfo = ZoneInfo(DEFAULT_TIMEZONE)
    resolved_value = value or datetime.now(timezone.utc)
    if resolved_value.tzinfo is None:
        resolved_value = resolved_value.replace(tzinfo=timezone.utc)
    localized = resolved_value.astimezone(tzinfo)
    return localized.strftime(fmt), tz_name


__all__ = [
    "DEFAULT_TIMEZONE",
    "format_datetime_for_user",
    "resolve_user_timezone",
    "resolve_user_timezone_info",
    "validate_timezone_name",
]
