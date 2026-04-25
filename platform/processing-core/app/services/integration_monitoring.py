from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

from sqlalchemy import and_, func, case
from sqlalchemy.orm import Session

from app.models.external_request_log import ExternalRequestLog
from app.models.partner import Partner


def log_external_request(
    db: Session,
    *,
    partner_id: str,
    azs_id: str | None,
    terminal_id: str | None,
    operation_id: str | None,
    request_type: str,
    amount: int | None,
    liters: float | None,
    currency: str | None,
    status: str,
    reason_category: str | None,
    risk_code: str | None,
    limit_code: str | None,
    latency_ms: float | None,
) -> ExternalRequestLog:
    record = ExternalRequestLog(
        partner_id=partner_id,
        azs_id=azs_id,
        terminal_id=terminal_id,
        operation_id=operation_id,
        request_type=request_type,
        amount=amount,
        liters=liters,
        currency=currency,
        status=status,
        reason_category=reason_category,
        risk_code=risk_code,
        limit_code=limit_code,
        latency_ms=latency_ms,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _window_filter(query, window_minutes: int) -> Iterable[ExternalRequestLog]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=window_minutes)
    return query.filter(ExternalRequestLog.created_at >= since)


def partner_status_summary(db: Session, window_minutes: int = 15) -> List[dict]:
    base = _window_filter(db.query(ExternalRequestLog), window_minutes)
    grouped = (
        base.with_entities(
            ExternalRequestLog.partner_id,
            func.count().label("total"),
            func.sum(case((ExternalRequestLog.status.in_(["ERROR", "TIMEOUT"]), 1), else_=0)).label(
                "errors"
            ),
            func.avg(ExternalRequestLog.latency_ms).label("avg_latency"),
        )
        .group_by(ExternalRequestLog.partner_id)
        .all()
    )

    partners = {p.id: p for p in db.query(Partner).all()}
    summaries: List[dict] = []
    for row in grouped:
        error_rate = (row.errors or 0) / row.total if row.total else 0.0
        derived_status = _derive_partner_status(row.total, error_rate, row.avg_latency or 0)
        summaries.append(
            {
                "partner_id": row.partner_id,
                "partner_name": partners.get(
                    row.partner_id,
                    Partner(
                        id=row.partner_id,
                        name=row.partner_id,
                        type="AZS",
                        code=row.partner_id,
                        legal_name=row.partner_id,
                        partner_type="OTHER",
                        status="ACTIVE",
                        contacts={},
                    ),
                ).name,
                "status": derived_status,
                "total_requests": row.total,
                "error_rate": error_rate,
                "avg_latency_ms": row.avg_latency or 0,
            }
        )
    return summaries


def _derive_partner_status(total: int, error_rate: float, avg_latency: float) -> str:
    if total == 0:
        return "OFFLINE"
    if error_rate >= 0.3 or avg_latency > 1500:
        return "DEGRADED"
    if error_rate == 1:
        return "OFFLINE"
    return "ONLINE"


def azs_stats(db: Session, *, window_minutes: int, partner_id: Optional[str] = None) -> List[dict]:
    base = _window_filter(db.query(ExternalRequestLog), window_minutes)
    if partner_id:
        base = base.filter(ExternalRequestLog.partner_id == partner_id)

    grouped = (
        base.with_entities(
            ExternalRequestLog.azs_id.label("azs_id"),
            func.count().label("total"),
            func.sum(case((ExternalRequestLog.status == "DECLINED", 1), else_=0)).label("declines"),
            func.sum(
                case((ExternalRequestLog.reason_category == "RISK", 1), else_=0)
            ).label("declines_risk"),
            func.sum(
                case((ExternalRequestLog.reason_category == "LIMIT", 1), else_=0)
            ).label("declines_limit"),
            func.sum(
                case((ExternalRequestLog.reason_category == "TECHNICAL", 1), else_=0)
            ).label("declines_technical"),
            func.sum(
                case((ExternalRequestLog.reason_category == "PARTNER_ERROR", 1), else_=0)
            ).label("declines_partner"),
            func.sum(case((ExternalRequestLog.status.in_(["ERROR", "TIMEOUT"]), 1), else_=0)).label(
                "errors"
            ),
        )
        .group_by(ExternalRequestLog.azs_id)
        .all()
    )

    result: List[dict] = []
    for row in grouped:
        total = row.total or 0
        errors = row.errors or 0
        error_rate = errors / total if total else 0.0
        result.append(
            {
                "azs_id": row.azs_id,
                "total_requests": total,
                "declines_total": row.declines or 0,
                "declines_by_category": {
                    "RISK": row.declines_risk or 0,
                    "LIMIT": row.declines_limit or 0,
                    "TECHNICAL": row.declines_technical or 0,
                    "PARTNER_ERROR": row.declines_partner or 0,
                },
                "error_rate": error_rate,
            }
        )
    return result


def query_requests(
    db: Session,
    *,
    partner_id: Optional[str] = None,
    azs_id: Optional[str] = None,
    status: Optional[str] = None,
    reason_category: Optional[str] = None,
    dt_from: Optional[datetime] = None,
    dt_to: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = db.query(ExternalRequestLog)
    if partner_id:
        query = query.filter(ExternalRequestLog.partner_id == partner_id)
    if azs_id:
        query = query.filter(ExternalRequestLog.azs_id == azs_id)
    if status:
        query = query.filter(ExternalRequestLog.status == status)
    if reason_category:
        query = query.filter(ExternalRequestLog.reason_category == reason_category)
    if dt_from:
        query = query.filter(ExternalRequestLog.created_at >= dt_from)
    if dt_to:
        query = query.filter(ExternalRequestLog.created_at <= dt_to)

    total = query.count()
    items = (
        query.order_by(ExternalRequestLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def recent_declines(
    db: Session,
    *,
    since: datetime,
    partner_id: Optional[str] = None,
    reason_category: Optional[str] = None,
):
    query = db.query(ExternalRequestLog).filter(
        and_(ExternalRequestLog.created_at >= since, ExternalRequestLog.status == "DECLINED")
    )
    if partner_id:
        query = query.filter(ExternalRequestLog.partner_id == partner_id)
    if reason_category:
        query = query.filter(ExternalRequestLog.reason_category == reason_category)
    return query.order_by(ExternalRequestLog.created_at.desc()).all()
