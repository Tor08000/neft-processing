from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from time import perf_counter
from typing import Iterable

from fastapi import HTTPException
from neft_shared.logging_setup import get_logger
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.domains.documents.models import DocumentEdoState, DocumentStatus, EdoStatus
from app.domains.documents.models import ClientDocument as Document
from app.models.fleet import FleetDriver
from app.models.fuel import FuelCard, FuelStation, FuelTransaction, FuelTransactionStatus
from app.models.bi import (
    BiDailyMetric,
    BiDeclineEvent,
    BiExportBatch,
    BiExportKind,
    BiExportStatus,
    BiMartCashflow,
    BiMartClientSpend,
    BiMartFinanceDaily,
    BiMartOpsSla,
    BiMartPartnerPerformance,
    BiMartVersion,
    BiOrderEvent,
    BiScopeType,
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


def _optional_mart_version(db: Session, mart_name: str) -> str | None:
    row = (
        db.query(BiMartVersion)
        .filter(BiMartVersion.mart_name == mart_name)
        .filter(BiMartVersion.is_active.is_(True))
        .order_by(BiMartVersion.created_at.desc())
        .first()
    )
    return row.version if row else None



def _log_query(name: str, started_at: float, trace_id: str | None) -> None:
    elapsed = perf_counter() - started_at
    bi_metrics.mark_query_latency(elapsed)
    logger.info(
        "bi.dashboard_query",
        extra={"dashboard": name, "duration_seconds": elapsed, "trace_id": trace_id},
    )



def _datetime_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def _to_minor(value: object | None) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(float(value))


def _rank_amounts(items: dict[str, int], *, key: str = "name", limit: int = 5) -> list[dict]:
    return [
        {key: name, "amount": amount}
        for name, amount in sorted(items.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]



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



def _document_attention(
    db: Session,
    *,
    tenant_id: int,
    client_id: str | None,
    date_from: date,
    date_to: date,
) -> tuple[int, list[dict]]:
    if not client_id:
        return 0, []

    query = (
        db.query(Document)
        .outerjoin(DocumentEdoState, DocumentEdoState.document_id == Document.id)
        .filter(Document.tenant_id == tenant_id)
        .filter(Document.client_id == client_id)
        .filter(Document.date.isnot(None))
        .filter(Document.date >= date_from)
        .filter(Document.date <= date_to)
        .filter(
            or_(
                Document.status.in_(
                    {
                        DocumentStatus.READY_TO_SIGN.value,
                        DocumentStatus.REJECTED.value,
                    }
                ),
                DocumentEdoState.edo_status.in_(
                    {
                        EdoStatus.ERROR.value,
                        EdoStatus.REJECTED.value,
                        EdoStatus.EDO_NOT_CONFIGURED.value,
                        EdoStatus.PROVIDER_UNAVAILABLE.value,
                    }
                ),
            )
        )
        .order_by(Document.updated_at.desc(), Document.created_at.desc())
    )
    rows = query.all()
    items = [
        {
            "id": doc.id,
            "title": doc.title,
            "description": f"Status: {doc.status}",
            "href": f"/documents/{doc.id}",
            "severity": "warning",
        }
        for doc in rows[:5]
    ]
    return len(rows), items



def _export_attention(
    db: Session,
    *,
    tenant_id: int,
    scope_type: BiScopeType,
    scope_id: str,
    date_from: date,
    date_to: date,
) -> tuple[int, list[dict]]:
    query = (
        db.query(BiExportBatch)
        .filter(BiExportBatch.tenant_id == tenant_id)
        .filter(BiExportBatch.date_from <= date_to)
        .filter(BiExportBatch.date_to >= date_from)
        .filter(BiExportBatch.status.in_({BiExportStatus.FAILED, BiExportStatus.CREATED, BiExportStatus.GENERATED}))
    )
    if scope_type == BiScopeType.CLIENT:
        query = query.filter(BiExportBatch.scope_type == BiScopeType.CLIENT).filter(BiExportBatch.scope_id == scope_id)
    elif scope_type == BiScopeType.PARTNER:
        query = query.filter(BiExportBatch.scope_type == BiScopeType.PARTNER).filter(BiExportBatch.scope_id == scope_id)
    else:
        query = query.filter(
            or_(
                and_(BiExportBatch.scope_type == scope_type, BiExportBatch.scope_id == scope_id),
                BiExportBatch.scope_type == BiScopeType.TENANT,
            )
        )
    rows = query.order_by(BiExportBatch.created_at.desc()).all()
    items = [
        {
            "id": export.id,
            "title": f"Export {export.id}",
            "description": f"Status: {export.status.value}",
            "href": "/analytics/exports",
            "severity": "warning" if export.status == BiExportStatus.FAILED else "info",
        }
        for export in rows[:3]
    ]
    return len(rows), items



def client_daily_metrics_summary(
    db: Session,
    *,
    tenant_id: int,
    scope_type: BiScopeType,
    scope_id: str,
    date_from: date,
    date_to: date,
    trace_id: str | None,
) -> tuple[dict, str]:
    started_at = perf_counter()
    metrics_rows: list[BiDailyMetric] = (
        db.query(BiDailyMetric)
        .filter(BiDailyMetric.tenant_id == tenant_id)
        .filter(BiDailyMetric.scope_type == scope_type)
        .filter(BiDailyMetric.scope_id == scope_id)
        .filter(BiDailyMetric.date >= date_from)
        .filter(BiDailyMetric.date <= date_to)
        .order_by(BiDailyMetric.date.asc())
        .all()
    )
    spend_total = 0
    orders_total = 0
    orders_completed = 0
    refunds_total = 0
    declines_total = 0
    spend_series: list[dict] = []
    orders_series: list[dict] = []
    declines_series: list[dict] = []
    for row in metrics_rows:
        spend_value = int(row.spend_total or 0)
        orders_value = int(row.orders_total or 0)
        declines_value = int(row.declines_total or 0)
        spend_total += spend_value
        orders_total += orders_value
        orders_completed += int(row.orders_completed or 0)
        refunds_total += int(row.refunds_total or 0)
        declines_total += declines_value
        spend_series.append({"date": row.date, "value": spend_value})
        orders_series.append({"date": row.date, "value": orders_value})
        declines_series.append({"date": row.date, "value": declines_value})

    start_dt, end_dt = _datetime_bounds(date_from, date_to)
    decline_query = (
        db.query(BiDeclineEvent)
        .filter(BiDeclineEvent.tenant_id == tenant_id)
        .filter(BiDeclineEvent.occurred_at >= start_dt)
        .filter(BiDeclineEvent.occurred_at < end_dt)
    )
    if scope_type == BiScopeType.CLIENT:
        decline_query = decline_query.filter(BiDeclineEvent.client_id == scope_id)
    elif scope_type == BiScopeType.PARTNER:
        decline_query = decline_query.filter(BiDeclineEvent.partner_id == scope_id)
    decline_rows = decline_query.all()
    reasons: dict[str, int] = defaultdict(int)
    for row in decline_rows:
        reasons[row.primary_reason or "UNKNOWN"] += 1
    top_reason = max(reasons.items(), key=lambda item: item[1])[0] if reasons else None

    documents_attention, document_items = _document_attention(
        db,
        tenant_id=tenant_id,
        client_id=scope_id if scope_type == BiScopeType.CLIENT else None,
        date_from=date_from,
        date_to=date_to,
    )
    exports_attention, export_items = _export_attention(
        db,
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        date_from=date_from,
        date_to=date_to,
    )
    response = {
        "from": date_from,
        "to": date_to,
        "currency": "RUB",
        "spend": {"total": spend_total, "series": spend_series},
        "orders": {
            "total": orders_total,
            "completed": orders_completed,
            "refunds": refunds_total,
            "series": orders_series,
        },
        "declines": {
            "total": declines_total,
            "top_reason": top_reason,
            "series": declines_series,
        },
        "documents": {"attention": documents_attention},
        "exports": {"attention": exports_attention},
        "attention": [*document_items, *export_items][:5],
    }
    _log_query("client_daily_metrics_summary", started_at, trace_id)
    return response, _mart_version(db, "bi_daily_metrics")



def client_declines_summary(
    db: Session,
    *,
    tenant_id: int,
    client_id: str | None,
    date_from: date,
    date_to: date,
    reason: str | None,
    station_id: str | None,
    trace_id: str | None,
) -> dict:
    started_at = perf_counter()
    start_dt, end_dt = _datetime_bounds(date_from, date_to)
    query = (
        db.query(BiDeclineEvent)
        .filter(BiDeclineEvent.tenant_id == tenant_id)
        .filter(BiDeclineEvent.occurred_at >= start_dt)
        .filter(BiDeclineEvent.occurred_at < end_dt)
    )
    if client_id:
        query = query.filter(BiDeclineEvent.client_id == client_id)
    if reason:
        query = query.filter(BiDeclineEvent.primary_reason == reason)
    if station_id:
        query = query.filter(BiDeclineEvent.station_id == station_id)
    rows: list[BiDeclineEvent] = query.order_by(BiDeclineEvent.occurred_at.asc()).all()

    top_reasons: dict[str, int] = defaultdict(int)
    trend: dict[tuple[date, str], int] = defaultdict(int)
    heatmap: dict[tuple[str, str], int] = defaultdict(int)
    expensive_rows: list[dict] = []
    for row in rows:
        resolved_reason = row.primary_reason or "UNKNOWN"
        resolved_station = row.station_id or "UNKNOWN"
        event_date = row.occurred_at.date()
        top_reasons[resolved_reason] += 1
        trend[(event_date, resolved_reason)] += 1
        heatmap[(resolved_station, resolved_reason)] += 1
        expensive_rows.append(
            {
                "id": row.operation_id,
                "reason": resolved_reason,
                "amount": int(row.amount or 0),
                "station": None if row.station_id is None else row.station_id,
            }
        )

    response = {
        "total": len(rows),
        "top_reasons": [
            {"reason": reason_name, "count": count}
            for reason_name, count in sorted(top_reasons.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        "trend": [
            {"date": item_date, "reason": reason_name, "count": count}
            for (item_date, reason_name), count in sorted(trend.items(), key=lambda item: (item[0][0], item[0][1]))
        ],
        "heatmap": [
            {"station": station_name, "reason": reason_name, "count": count}
            for (station_name, reason_name), count in sorted(heatmap.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))[:20]
        ],
        "expensive": sorted(expensive_rows, key=lambda item: (-item["amount"], item["id"]))[:10],
    }
    _log_query("client_declines_summary", started_at, trace_id)
    return response



def client_orders_summary(
    db: Session,
    *,
    tenant_id: int,
    client_id: str | None,
    date_from: date,
    date_to: date,
    status: str | None,
    trace_id: str | None,
) -> dict:
    started_at = perf_counter()
    start_dt, end_dt = _datetime_bounds(date_from, date_to)
    query = (
        db.query(BiOrderEvent)
        .filter(BiOrderEvent.tenant_id == tenant_id)
        .filter(BiOrderEvent.occurred_at >= start_dt)
        .filter(BiOrderEvent.occurred_at < end_dt)
    )
    if client_id:
        query = query.filter(BiOrderEvent.client_id == client_id)
    if status:
        query = query.filter(BiOrderEvent.status_after == status)
    rows: list[BiOrderEvent] = query.order_by(BiOrderEvent.occurred_at.asc()).all()

    completed_statuses = {"CAPTURED", "COMPLETED", "PAID", "DELIVERED", "SUCCESS", "CLOSED"}
    cancelled_statuses = {"CANCELLED", "CANCELED", "REJECTED"}
    top_services: dict[str, int] = defaultdict(int)
    status_breakdown: dict[str, int] = defaultdict(int)
    completed_amount_sum = 0
    completed_count = 0
    cancelled_count = 0
    refunds_count = 0
    for row in rows:
        resolved_status = row.status_after or row.event_type or "UNKNOWN"
        resolved_service = row.service_id
        if not resolved_service and isinstance(row.payload, dict):
            resolved_service = row.payload.get("product_type") or row.payload.get("operation_type")
        resolved_service = resolved_service or row.offer_id or "UNKNOWN"
        top_services[str(resolved_service)] += 1
        status_breakdown[resolved_status] += 1
        if resolved_status in completed_statuses:
            completed_count += 1
            completed_amount_sum += int(row.amount or 0)
        if resolved_status in cancelled_statuses:
            cancelled_count += 1
        if "REFUND" in resolved_status.upper() or "REFUND" in (row.event_type or "").upper():
            refunds_count += 1

    avg_order_value = int(completed_amount_sum / completed_count) if completed_count else 0
    total = len(rows)
    refunds_rate = int(round((refunds_count / total) * 100)) if total else 0
    response = {
        "total": total,
        "completed": completed_count,
        "cancelled": cancelled_count,
        "refunds_rate": refunds_rate,
        "refunds_count": refunds_count,
        "avg_order_value": avg_order_value,
        "top_services": [
            {"name": service_name, "orders": count}
            for service_name, count in sorted(top_services.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        "status_breakdown": [
            {"status": status_name, "count": count}
            for status_name, count in sorted(status_breakdown.items(), key=lambda item: (-item[1], item[0]))
        ],
    }
    _log_query("client_orders_summary", started_at, trace_id)
    return response


def client_documents_summary(
    db: Session,
    *,
    tenant_id: int,
    client_id: str | None,
    date_from: date,
    date_to: date,
    trace_id: str | None,
) -> dict:
    started_at = perf_counter()
    if not client_id:
        response = {"issued": 0, "signed": 0, "edo_pending": 0, "edo_failed": 0, "attention": []}
        _log_query("client_documents_summary", started_at, trace_id)
        return response

    rows = (
        db.query(Document, DocumentEdoState)
        .outerjoin(DocumentEdoState, DocumentEdoState.document_id == Document.id)
        .filter(Document.tenant_id == tenant_id)
        .filter(Document.client_id == client_id)
        .filter(Document.date.isnot(None))
        .filter(Document.date >= date_from)
        .filter(Document.date <= date_to)
        .order_by(Document.updated_at.desc(), Document.created_at.desc())
        .all()
    )

    signed_statuses = {
        DocumentStatus.SIGNED.value,
        DocumentStatus.SIGNED_CLIENT.value,
        DocumentStatus.CLOSED.value,
    }
    pending_edo_statuses = {
        EdoStatus.NEW.value,
        EdoStatus.SENDING.value,
        EdoStatus.QUEUED.value,
        EdoStatus.SENT.value,
        EdoStatus.DELIVERED.value,
    }
    failed_edo_statuses = {
        EdoStatus.ERROR.value,
        EdoStatus.REJECTED.value,
        EdoStatus.EDO_NOT_CONFIGURED.value,
        EdoStatus.PROVIDER_UNAVAILABLE.value,
    }

    issued = 0
    signed = 0
    edo_pending = 0
    edo_failed = 0
    attention: list[dict] = []

    for document, edo_state in rows:
        document_status = str(document.status)
        edo_status = edo_state.edo_status if edo_state else None
        if document_status not in {DocumentStatus.DRAFT.value, DocumentStatus.CANCELLED.value}:
            issued += 1
        if (
            document_status in signed_statuses
            or edo_status == EdoStatus.SIGNED.value
            or document.signed_by_client_at is not None
        ):
            signed += 1
        if edo_status in pending_edo_statuses or document_status == DocumentStatus.READY_TO_SIGN.value:
            edo_pending += 1
        if document_status == DocumentStatus.REJECTED.value or edo_status in failed_edo_statuses:
            edo_failed += 1

        requires_attention = document_status == DocumentStatus.READY_TO_SIGN.value or edo_status in failed_edo_statuses
        if requires_attention:
            attention.append(
                {
                    "id": document.id,
                    "title": document.title,
                    "status": edo_status or document_status,
                }
            )

    attention_priority = {
        EdoStatus.ERROR.value: 0,
        EdoStatus.REJECTED.value: 0,
        EdoStatus.EDO_NOT_CONFIGURED.value: 0,
        EdoStatus.PROVIDER_UNAVAILABLE.value: 0,
        DocumentStatus.REJECTED.value: 0,
        DocumentStatus.READY_TO_SIGN.value: 1,
    }
    attention.sort(key=lambda item: (attention_priority.get(str(item["status"]), 2), str(item["title"]), str(item["id"])))

    response = {
        "issued": issued,
        "signed": signed,
        "edo_pending": edo_pending,
        "edo_failed": edo_failed,
        "attention": attention[:10],
    }
    _log_query("client_documents_summary", started_at, trace_id)
    return response


def _summary_export_status(status: BiExportStatus) -> str:
    if status == BiExportStatus.FAILED:
        return "MISMATCH"
    if status == BiExportStatus.CREATED:
        return "PENDING"
    return "OK"


def _export_mapping_version(db: Session, kind: BiExportKind) -> str | None:
    mart_names = {
        BiExportKind.DAILY_METRICS: "bi_daily_metrics",
        BiExportKind.ORDERS: "bi_order_events",
        BiExportKind.ORDER_EVENTS: "bi_order_events",
        BiExportKind.DECLINES: "bi_decline_events",
        BiExportKind.PAYOUTS: "bi_payout_events",
    }
    mart_name = mart_names.get(kind)
    if not mart_name:
        return None
    return _optional_mart_version(db, mart_name)


def client_exports_summary(
    db: Session,
    *,
    tenant_id: int,
    client_id: str | None,
    date_from: date,
    date_to: date,
    trace_id: str | None,
) -> dict:
    started_at = perf_counter()
    if not client_id:
        response = {"total": 0, "ok": 0, "mismatch": 0, "items": []}
        _log_query("client_exports_summary", started_at, trace_id)
        return response

    rows: list[BiExportBatch] = (
        db.query(BiExportBatch)
        .filter(BiExportBatch.tenant_id == tenant_id)
        .filter(BiExportBatch.scope_type == BiScopeType.CLIENT)
        .filter(BiExportBatch.scope_id == client_id)
        .filter(BiExportBatch.date_from <= date_to)
        .filter(BiExportBatch.date_to >= date_from)
        .order_by(BiExportBatch.created_at.desc())
        .all()
    )

    ok_count = 0
    mismatch_count = 0
    items: list[dict] = []
    for export in rows[:20]:
        status = _summary_export_status(export.status)
        if status == "OK":
            ok_count += 1
        elif status == "MISMATCH":
            mismatch_count += 1
        items.append(
            {
                "id": export.id,
                "status": status,
                "checksum": export.sha256,
                "mapping_version": _export_mapping_version(db, export.kind),
                "created_at": export.created_at if export.created_at.tzinfo else export.created_at.replace(tzinfo=timezone.utc),
            }
        )

    response = {
        "total": len(rows),
        "ok": ok_count,
        "mismatch": mismatch_count,
        "items": items,
    }
    _log_query("client_exports_summary", started_at, trace_id)
    return response


def client_spend_summary(
    db: Session,
    *,
    tenant_id: int,
    client_id: str | None,
    date_from: date,
    date_to: date,
    trace_id: str | None,
) -> dict:
    started_at = perf_counter()
    mart_query = (
        db.query(BiMartClientSpend)
        .filter(BiMartClientSpend.tenant_id == tenant_id)
        .filter(BiMartClientSpend.period >= date_from)
        .filter(BiMartClientSpend.period <= date_to)
    )
    if client_id:
        mart_query = mart_query.filter(BiMartClientSpend.client_id == client_id)
    mart_rows: list[BiMartClientSpend] = mart_query.order_by(BiMartClientSpend.period.asc()).all()

    total_spend = 0
    trend: list[dict] = []
    product_totals: dict[str, int] = defaultdict(int)
    for row in mart_rows:
        spend_total = _to_minor(row.spend_total)
        total_spend += spend_total
        trend.append({"date": row.period, "value": spend_total})
        if isinstance(row.spend_by_product, dict):
            for product_name, amount in row.spend_by_product.items():
                product_totals[str(product_name)] += _to_minor(amount)

    station_totals: dict[str, int] = defaultdict(int)
    merchant_totals: dict[str, int] = defaultdict(int)
    card_totals: dict[str, int] = defaultdict(int)
    driver_totals: dict[str, int] = defaultdict(int)
    if client_id:
        start_dt, end_dt = _datetime_bounds(date_from, date_to)
        tx_rows = (
            db.query(FuelTransaction, FuelStation, FuelCard, FleetDriver)
            .outerjoin(FuelStation, FuelStation.id == FuelTransaction.station_id)
            .outerjoin(FuelCard, FuelCard.id == FuelTransaction.card_id)
            .outerjoin(FleetDriver, FleetDriver.id == FuelTransaction.driver_id)
            .filter(FuelTransaction.tenant_id == tenant_id)
            .filter(FuelTransaction.client_id == client_id)
            .filter(FuelTransaction.occurred_at >= start_dt)
            .filter(FuelTransaction.occurred_at < end_dt)
            .filter(FuelTransaction.status == FuelTransactionStatus.SETTLED)
            .all()
        )

        for transaction, station, card, driver in tx_rows:
            amount = _to_minor(transaction.amount_total_minor or transaction.amount)
            station_name = (station.name if station else None) or transaction.station_external_id or "UNKNOWN"
            merchant_name = transaction.merchant_name or transaction.merchant_key or "UNKNOWN"
            card_name = (card.card_alias if card else None) or (card.masked_pan if card else None) or str(transaction.card_id)
            driver_name = (driver.full_name if driver else None) or (str(transaction.driver_id) if transaction.driver_id else None)

            station_totals[station_name] += amount
            merchant_totals[merchant_name] += amount
            card_totals[card_name] += amount
            if driver_name:
                driver_totals[driver_name] += amount

    day_span = max((date_to - date_from).days + 1, 1)
    response = {
        "currency": "RUB",
        "total_spend": total_spend,
        "avg_daily_spend": int(round(total_spend / day_span)) if total_spend else 0,
        "trend": trend,
        "top_stations": _rank_amounts(station_totals),
        "top_merchants": _rank_amounts(merchant_totals),
        "top_cards": _rank_amounts(card_totals),
        "top_drivers": _rank_amounts(driver_totals),
        "product_breakdown": _rank_amounts(product_totals, key="product"),
        "export_available": False,
        "export_dataset": "spend",
    }
    _log_query("client_spend_summary", started_at, trace_id)
    return response


__all__ = [
    "CFO_ROLES",
    "OPS_ROLES",
    "PARTNER_ROLES",
    "CLIENT_ROLES",
    "_require_role",
    "client_daily_metrics_summary",
    "client_declines_summary",
    "client_orders_summary",
    "cfo_cashflow",
    "cfo_overview",
    "client_spend",
    "ops_sla",
    "partner_performance",
]
