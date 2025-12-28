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

    base_query = select(OpsEscalation).where(
        OpsEscalation.tenant_id == tenant_id,
        OpsEscalation.created_at >= start,
        OpsEscalation.created_at <= end,
    )

    opened = db.execute(select(func.count()).select_from(base_query.subquery())).scalar_one()

    acked = (
        db.execute(
            select(func.count())
            .select_from(OpsEscalation)
            .where(
                OpsEscalation.tenant_id == tenant_id,
                OpsEscalation.acked_at.isnot(None),
                OpsEscalation.acked_at >= start,
                OpsEscalation.acked_at <= end,
            )
        )
        .scalar_one()
    )

    closed = (
        db.execute(
            select(func.count())
            .select_from(OpsEscalation)
            .where(
                OpsEscalation.tenant_id == tenant_id,
                OpsEscalation.closed_at.isnot(None),
                OpsEscalation.closed_at >= start,
                OpsEscalation.closed_at <= end,
            )
        )
        .scalar_one()
    )

    overdue = (
        db.execute(
            select(func.count())
            .select_from(OpsEscalation)
            .where(
                OpsEscalation.tenant_id == tenant_id,
                OpsEscalation.created_at >= start,
                OpsEscalation.created_at <= end,
                OpsEscalation.sla_expires_at.isnot(None),
                OpsEscalation.sla_expires_at <= current_time,
                OpsEscalation.status != OpsEscalationStatus.CLOSED,
            )
        )
        .scalar_one()
    )

    closed_within_sla = (
        db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                OpsEscalation.closed_at.isnot(None)
                                & OpsEscalation.sla_expires_at.isnot(None)
                                & (OpsEscalation.closed_at <= OpsEscalation.sla_expires_at),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                )
            )
            .select_from(OpsEscalation)
            .where(
                OpsEscalation.tenant_id == tenant_id,
                OpsEscalation.created_at >= start,
                OpsEscalation.created_at <= end,
            )
        )
        .scalar_one()
    )

    avg_time_to_ack = (
        db.execute(
            select(func.avg(_minutes_diff_expr(db, OpsEscalation.created_at, OpsEscalation.acked_at)))
            .select_from(OpsEscalation)
            .where(
                OpsEscalation.tenant_id == tenant_id,
                OpsEscalation.acked_at.isnot(None),
                OpsEscalation.created_at >= start,
                OpsEscalation.created_at <= end,
            )
        )
        .scalar_one()
    )

    avg_time_to_close = (
        db.execute(
            select(func.avg(_minutes_diff_expr(db, OpsEscalation.created_at, OpsEscalation.closed_at)))
            .select_from(OpsEscalation)
            .where(
                OpsEscalation.tenant_id == tenant_id,
                OpsEscalation.closed_at.isnot(None),
                OpsEscalation.created_at >= start,
                OpsEscalation.created_at <= end,
            )
        )
        .scalar_one()
    )

    def _breakdown(column):
        rows = (
            db.execute(
                select(column, func.count())
                .select_from(OpsEscalation)
                .where(
                    OpsEscalation.tenant_id == tenant_id,
                    OpsEscalation.created_at >= start,
                    OpsEscalation.created_at <= end,
                    column.isnot(None),
                )
                .group_by(column)
            )
            .all()
        )
        return {str(key): int(count) for key, count in rows}

    return {
        "totals": {
            "opened": int(opened or 0),
            "acked": int(acked or 0),
            "closed": int(closed or 0),
            "overdue": int(overdue or 0),
        },
        "sla": {
            "closed_within_sla": int(closed_within_sla or 0),
            "avg_time_to_ack_minutes": float(avg_time_to_ack) if avg_time_to_ack is not None else None,
            "avg_time_to_close_minutes": float(avg_time_to_close) if avg_time_to_close is not None else None,
        },
        "breakdown": {
            "by_primary_reason": _breakdown(OpsEscalation.primary_reason),
            "by_target": _breakdown(OpsEscalation.target),
            "by_close_reason_code": _breakdown(OpsEscalation.close_reason_code),
            "by_ack_reason_code": _breakdown(OpsEscalation.ack_reason_code),
        },
    }


__all__ = ["build_kpi_report"]
