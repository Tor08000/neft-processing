from __future__ import annotations

from datetime import date
from time import perf_counter
from typing import Iterable

from fastapi import HTTPException
from neft_shared.logging_setup import get_logger
from sqlalchemy.orm import Session

from app.models.bi import (
    BiMartCashflow,
    BiMartClientSpend,
    BiMartFinanceDaily,
    BiMartOpsSla,
    BiMartPartnerPerformance,
    BiMartVersion,
)
from app.services.bi.metrics import metrics as bi_metrics

logger = get_logger(__name__)


CFO_ROLES = {"CFO", "FINANCE"}
OPS_ROLES = {"OPS", "OPERATIONS"}
PARTNER_ROLES = {"PARTNER"}
CLIENT_ROLES = {"CLIENT"}


def _normalize_roles(token: dict) -> set[str]:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = token.get("role")
    if role and role not in roles:
        roles.append(role)
    return {str(item).upper() for item in roles}


def _require_role(token: dict, required: set[str]) -> None:
    roles = _normalize_roles(token)
    if roles.intersection(required):
        return
    raise HTTPException(status_code=403, detail="forbidden")


def _mart_version(db: Session, mart_name: str) -> str:
    row = (
        db.query(BiMartVersion)
        .filter(BiMartVersion.mart_name == mart_name)
        .filter(BiMartVersion.is_active.is_(True))
        .order_by(BiMartVersion.created_at.desc())
        .first()
    )
    return row.version if row else "v1"


def _log_query(name: str, started_at: float, trace_id: str | None) -> None:
    elapsed = perf_counter() - started_at
    bi_metrics.mark_query_latency(elapsed)
    logger.info(
        "bi.dashboard_query",
        extra={"dashboard": name, "duration_seconds": elapsed, "trace_id": trace_id},
    )


def cfo_overview(
    db: Session,
    *,
    tenant_id: int,
    date_from: date,
    date_to: date,
    trace_id: str | None,
) -> tuple[dict, list[dict], str]:
    started_at = perf_counter()
    rows: Iterable[BiMartFinanceDaily] = (
        db.query(BiMartFinanceDaily)
        .filter(BiMartFinanceDaily.tenant_id == tenant_id)
        .filter(BiMartFinanceDaily.date >= date_from)
        .filter(BiMartFinanceDaily.date <= date_to)
        .order_by(BiMartFinanceDaily.date.asc())
        .all()
    )
    totals = {
        "gross_revenue": 0,
        "net_revenue": 0,
        "commission_income": 0,
        "vat": 0,
        "refunds": 0,
        "penalties": 0,
        "margin": 0,
    }
    series: list[dict] = []
    for row in rows:
        totals["gross_revenue"] += int(row.gross_revenue or 0)
        totals["net_revenue"] += int(row.net_revenue or 0)
        totals["commission_income"] += int(row.commission_income or 0)
        totals["vat"] += int(row.vat or 0)
        totals["refunds"] += int(row.refunds or 0)
        totals["penalties"] += int(row.penalties or 0)
        totals["margin"] += int(row.margin or 0)
        series.append(
            {
                "date": row.date,
                "gross_revenue": int(row.gross_revenue or 0),
                "net_revenue": int(row.net_revenue or 0),
                "commission_income": int(row.commission_income or 0),
                "vat": int(row.vat or 0),
                "refunds": int(row.refunds or 0),
                "penalties": int(row.penalties or 0),
                "margin": int(row.margin or 0),
            }
        )
    _log_query("cfo_overview", started_at, trace_id)
    return totals, series, _mart_version(db, "mart_finance_daily")


def cfo_cashflow(
    db: Session,
    *,
    tenant_id: int,
    date_from: date,
    date_to: date,
    trace_id: str | None,
) -> tuple[dict, list[dict], str]:
    started_at = perf_counter()
    rows: Iterable[BiMartCashflow] = (
        db.query(BiMartCashflow)
        .filter(BiMartCashflow.tenant_id == tenant_id)
        .filter(BiMartCashflow.date >= date_from)
        .filter(BiMartCashflow.date <= date_to)
        .order_by(BiMartCashflow.date.asc())
        .all()
    )
    totals = {
        "inflow": 0,
        "outflow": 0,
        "net_cashflow": 0,
        "balance_estimated": 0,
    }
    series: list[dict] = []
    for row in rows:
        totals["inflow"] += int(row.inflow or 0)
        totals["outflow"] += int(row.outflow or 0)
        totals["net_cashflow"] += int(row.net_cashflow or 0)
        totals["balance_estimated"] += int(row.balance_estimated or 0)
        series.append(
            {
                "date": row.date,
                "inflow": int(row.inflow or 0),
                "outflow": int(row.outflow or 0),
                "net_cashflow": int(row.net_cashflow or 0),
                "balance_estimated": int(row.balance_estimated or 0),
            }
        )
    _log_query("cfo_cashflow", started_at, trace_id)
    return totals, series, _mart_version(db, "mart_cashflow")


def ops_sla(
    db: Session,
    *,
    tenant_id: int,
    date_from: date,
    date_to: date,
    trace_id: str | None,
) -> tuple[dict, list[dict], list[dict], str]:
    started_at = perf_counter()
    rows: Iterable[BiMartOpsSla] = (
        db.query(BiMartOpsSla)
        .filter(BiMartOpsSla.tenant_id == tenant_id)
        .filter(BiMartOpsSla.date >= date_from)
        .filter(BiMartOpsSla.date <= date_to)
        .order_by(BiMartOpsSla.date.asc())
        .all()
    )
    totals = {
        "total_orders": 0,
        "sla_breaches": 0,
        "avg_resolution_time": None,
        "p95_resolution_time": None,
    }
    series: list[dict] = []
    breaches_samples = 0
    avg_sum = 0.0
    p95_sum = 0.0
    top_partners: list[dict] = []
    for row in rows:
        totals["total_orders"] += int(row.total_orders or 0)
        totals["sla_breaches"] += int(row.sla_breaches or 0)
        if row.avg_resolution_time is not None:
            avg_sum += float(row.avg_resolution_time)
            breaches_samples += 1
        if row.p95_resolution_time is not None:
            p95_sum += float(row.p95_resolution_time)
        series.append(
            {
                "date": row.date,
                "total_orders": int(row.total_orders or 0),
                "sla_breaches": int(row.sla_breaches or 0),
                "avg_resolution_time": float(row.avg_resolution_time) if row.avg_resolution_time is not None else None,
                "p95_resolution_time": float(row.p95_resolution_time) if row.p95_resolution_time is not None else None,
            }
        )
        if row.top_partners_by_breaches:
            top_partners = list(row.top_partners_by_breaches)
    if breaches_samples:
        totals["avg_resolution_time"] = avg_sum / breaches_samples
        totals["p95_resolution_time"] = p95_sum / breaches_samples if breaches_samples else None
    _log_query("ops_sla", started_at, trace_id)
    return totals, series, top_partners, _mart_version(db, "mart_ops_sla")


def partner_performance(
    db: Session,
    *,
    tenant_id: int,
    partner_id: str | None,
    date_from: date,
    date_to: date,
    trace_id: str | None,
) -> tuple[list[dict], str]:
    started_at = perf_counter()
    query = (
        db.query(BiMartPartnerPerformance)
        .filter(BiMartPartnerPerformance.tenant_id == tenant_id)
        .filter(BiMartPartnerPerformance.period >= date_from)
        .filter(BiMartPartnerPerformance.period <= date_to)
    )
    if partner_id:
        query = query.filter(BiMartPartnerPerformance.partner_id == partner_id)
    rows = query.order_by(BiMartPartnerPerformance.period.asc()).all()
    items = [
        {
            "partner_id": row.partner_id,
            "period": row.period,
            "orders_count": int(row.orders_count or 0),
            "revenue": int(row.revenue or 0),
            "penalties": int(row.penalties or 0),
            "payout_amount": int(row.payout_amount or 0),
            "sla_score": float(row.sla_score) if row.sla_score is not None else None,
        }
        for row in rows
    ]
    _log_query("partner_performance", started_at, trace_id)
    return items, _mart_version(db, "mart_partner_performance")


def client_spend(
    db: Session,
    *,
    tenant_id: int,
    client_id: str | None,
    date_from: date,
    date_to: date,
    trace_id: str | None,
) -> tuple[list[dict], str]:
    started_at = perf_counter()
    query = (
        db.query(BiMartClientSpend)
        .filter(BiMartClientSpend.tenant_id == tenant_id)
        .filter(BiMartClientSpend.period >= date_from)
        .filter(BiMartClientSpend.period <= date_to)
    )
    if client_id:
        query = query.filter(BiMartClientSpend.client_id == client_id)
    rows = query.order_by(BiMartClientSpend.period.asc()).all()
    items = [
        {
            "client_id": row.client_id,
            "period": row.period,
            "spend_total": int(row.spend_total or 0),
            "spend_by_product": row.spend_by_product,
            "fuel_spend": int(row.fuel_spend or 0),
            "marketplace_spend": int(row.marketplace_spend or 0),
            "avg_ticket": int(row.avg_ticket or 0),
        }
        for row in rows
    ]
    _log_query("client_spend", started_at, trace_id)
    return items, _mart_version(db, "mart_client_spend")


__all__ = [
    "CFO_ROLES",
    "OPS_ROLES",
    "PARTNER_ROLES",
    "CLIENT_ROLES",
    "_require_role",
    "cfo_cashflow",
    "cfo_overview",
    "client_spend",
    "ops_sla",
    "partner_performance",
]
