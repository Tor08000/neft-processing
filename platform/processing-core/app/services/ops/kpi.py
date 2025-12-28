from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.ops import OpsEscalation, OpsEscalationStatus


def _resolve_range(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
    return start, end


def _minutes_diff_expr(db: Session, start_col, end_col):
    dialect = db.bind.dialect.name if db.bind else ""
    if dialect == "sqlite":
        return (func.julianday(end_col) - func.julianday(start_col)) * 24 * 60
    return func.extract("epoch", end_col - start_col) / 60.0


def build_kpi_report(
    db: Session,
    *,
    tenant_id: int,
    date_from: date,
    date_to: date,
    now: datetime | None = None,
) -> dict:
    start, end = _resolve_range(date_from, date_to)
    current_time = now or datetime.now(timezone.utc)

    base_filters = (
        OpsEscalation.tenant_id == tenant_id,
        OpsEscalation.created_at >= start,
        OpsEscalation.created_at <= end,
    )

    violation_case = case(
        (
            (OpsEscalation.sla_expires_at.isnot(None))
            & (
                (OpsEscalation.closed_at.isnot(None) & (OpsEscalation.closed_at > OpsEscalation.sla_expires_at))
                | (OpsEscalation.closed_at.is_(None) & (OpsEscalation.sla_expires_at < current_time))
            ),
            1,
        ),
        else_=0,
    )

    avg_resolution_minutes = func.avg(_minutes_diff_expr(db, OpsEscalation.created_at, OpsEscalation.closed_at))

    reason_rows = (
        db.execute(
            select(
                OpsEscalation.primary_reason,
                func.coalesce(
                    func.sum(case((OpsEscalation.status != OpsEscalationStatus.CLOSED, 1), else_=0)), 0
                ).label("open_count"),
                func.coalesce(func.sum(violation_case), 0).label("violations"),
                avg_resolution_minutes.label("avg_resolution_minutes"),
            )
            .select_from(OpsEscalation)
            .where(*base_filters)
            .group_by(OpsEscalation.primary_reason)
        )
        .all()
    )

    by_reason: dict[str, dict[str, float | int]] = {}
    for primary_reason, open_count, violations, avg_minutes in reason_rows:
        payload: dict[str, float | int] = {"open": int(open_count or 0)}
        if violations is not None:
            payload["sla_violations"] = int(violations or 0)
        if avg_minutes is not None:
            payload["avg_resolution_hours"] = round(float(avg_minutes) / 60.0, 2)
        by_reason[str(primary_reason)] = payload

    team_rows = (
        db.execute(
            select(
                OpsEscalation.target,
                func.coalesce(
                    func.sum(case((OpsEscalation.status != OpsEscalationStatus.CLOSED, 1), else_=0)), 0
                ).label("open_count"),
            )
            .select_from(OpsEscalation)
            .where(*base_filters)
            .group_by(OpsEscalation.target)
        )
        .all()
    )
    by_team = {str(target): {"open": int(open_count or 0)} for target, open_count in team_rows}

    return {
        "by_reason": by_reason,
        "by_team": by_team,
    }


__all__ = ["build_kpi_report"]
