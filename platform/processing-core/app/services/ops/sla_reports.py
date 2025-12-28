from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.ops import OpsEscalation, OpsEscalationStatus
from app.models.unified_explain import PrimaryReason
from app.services.explain.sla import SLA_DEFINITIONS


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

    by_reason: dict[PrimaryReason, dict[str, int]] = defaultdict(lambda: {"total": 0, "overdue": 0})
    total = 0
    closed_within_sla = 0
    overdue = 0

    for escalation in items:
        total += 1
        by_reason[escalation.primary_reason]["total"] += 1

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
            by_reason[escalation.primary_reason]["overdue"] += 1

    return {
        "period": report_date.isoformat(),
        "total": total,
        "closed_within_sla": closed_within_sla,
        "overdue": overdue,
        "by_primary_reason": {
            reason: {"total": data["total"], "overdue": data["overdue"]}
            for reason, data in by_reason.items()
        },
    }


__all__ = ["build_sla_report"]
