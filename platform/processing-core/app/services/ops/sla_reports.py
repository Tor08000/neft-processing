from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.ops import OpsEscalation, OpsEscalationStatus
from app.models.unified_explain import PrimaryReason
from app.services.explain.sla import SLA_DEFINITIONS


@dataclass
class _SLAStats:
    total: int = 0
    overdue: int = 0
    ack_minutes_total: float = 0.0
    ack_count: int = 0
    close_minutes_total: float = 0.0
    close_count: int = 0


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _resolve_due_at(escalation: OpsEscalation) -> datetime | None:
    if escalation.sla_expires_at:
        return _ensure_timezone(escalation.sla_expires_at)
    if not escalation.sla_started_at:
        return None
    definition = SLA_DEFINITIONS.get(escalation.primary_reason)
    if not definition:
        return None
    return _ensure_timezone(escalation.sla_started_at) + timedelta(minutes=definition.timeout_minutes)


def _minutes_between(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end:
        return None
    return (_ensure_timezone(end) - _ensure_timezone(start)).total_seconds() / 60.0


def _avg_minutes(total: float, count: int) -> float | None:
    if count <= 0:
        return None
    return round(total / count, 2)


def _summarize(stats: _SLAStats) -> dict[str, float | int | None]:
    return {
        "total": stats.total,
        "overdue": stats.overdue,
        "sla_breaches": stats.overdue,
        "avg_time_to_ack": _avg_minutes(stats.ack_minutes_total, stats.ack_count),
        "avg_time_to_close": _avg_minutes(stats.close_minutes_total, stats.close_count),
    }


def build_sla_report(
    db: Session,
    *,
    tenant_id: int,
    period: date | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    report_date = period or datetime.now(timezone.utc).date()
    start = datetime.combine(report_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    current_time = now or datetime.now(timezone.utc)
    current_time = _ensure_timezone(current_time)

    items = (
        db.query(OpsEscalation)
        .filter(
            OpsEscalation.tenant_id == tenant_id,
            OpsEscalation.created_at >= start,
            OpsEscalation.created_at < end,
        )
        .all()
    )

    by_reason: dict[PrimaryReason, _SLAStats] = defaultdict(_SLAStats)
    by_team: dict[str, _SLAStats] = defaultdict(_SLAStats)
    by_client: dict[str, _SLAStats] = defaultdict(_SLAStats)
    total = 0
    closed_within_sla = 0
    overdue = 0
    ack_minutes_total = 0.0
    ack_count = 0
    close_minutes_total = 0.0
    close_count = 0
    has_client_data = False

    for escalation in items:
        total += 1
        by_reason[escalation.primary_reason].total += 1
        by_team[escalation.target.value].total += 1
        if escalation.client_id:
            by_client[escalation.client_id].total += 1
            has_client_data = True

        ack_minutes = _minutes_between(escalation.created_at, escalation.acked_at)
        if ack_minutes is not None:
            ack_minutes_total += ack_minutes
            ack_count += 1
            by_reason[escalation.primary_reason].ack_minutes_total += ack_minutes
            by_reason[escalation.primary_reason].ack_count += 1
            by_team[escalation.target.value].ack_minutes_total += ack_minutes
            by_team[escalation.target.value].ack_count += 1
            if escalation.client_id:
                by_client[escalation.client_id].ack_minutes_total += ack_minutes
                by_client[escalation.client_id].ack_count += 1

        close_minutes = _minutes_between(escalation.created_at, escalation.closed_at)
        if close_minutes is not None:
            close_minutes_total += close_minutes
            close_count += 1
            by_reason[escalation.primary_reason].close_minutes_total += close_minutes
            by_reason[escalation.primary_reason].close_count += 1
            by_team[escalation.target.value].close_minutes_total += close_minutes
            by_team[escalation.target.value].close_count += 1
            if escalation.client_id:
                by_client[escalation.client_id].close_minutes_total += close_minutes
                by_client[escalation.client_id].close_count += 1

        due_at = _resolve_due_at(escalation)
        if not due_at:
            continue
        is_overdue = False
        if escalation.status == OpsEscalationStatus.CLOSED and escalation.closed_at:
            closed_at = _ensure_timezone(escalation.closed_at)
            is_overdue = closed_at > due_at
            if not is_overdue:
                closed_within_sla += 1
        elif escalation.status != OpsEscalationStatus.CLOSED:
            is_overdue = current_time > due_at

        if is_overdue:
            overdue += 1
            by_reason[escalation.primary_reason].overdue += 1
            by_team[escalation.target.value].overdue += 1
            if escalation.client_id:
                by_client[escalation.client_id].overdue += 1

    return {
        "period": report_date.isoformat(),
        "total": total,
        "closed_within_sla": closed_within_sla,
        "overdue": overdue,
        "sla_breaches": overdue,
        "avg_time_to_ack": _avg_minutes(ack_minutes_total, ack_count),
        "avg_time_to_close": _avg_minutes(close_minutes_total, close_count),
        "by_primary_reason": {
            reason: _summarize(data)
            for reason, data in by_reason.items()
        },
        "by_team": {team: _summarize(data) for team, data in by_team.items()},
        "by_client": {client: _summarize(data) for client, data in by_client.items()} if has_client_data else None,
    }


__all__ = ["build_sla_report"]
