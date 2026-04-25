from datetime import date, datetime
import csv
from io import StringIO
from time import perf_counter

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models.operation import Operation
from app.schemas.reports import (
    BillingDailyReportItem,
    BillingSummaryItem,
    GroupBy,
    TurnoverReportResponse,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.reports import get_turnover_report
from app.services.audit_service import AuditService, request_context_from_request
from neft_shared.logging_setup import get_logger
from app.services.billing_periods import BillingPeriodConflict
from app.services.reports_billing import (
    build_billing_summary_for_date,
    list_billing_summaries,
)
from app.services.reports_route_metrics import metrics as reports_route_metrics

logger = get_logger(__name__)


# Compatibility reports/export family over billing projections in processing-core.
# Canonical authoritative billing-summary read/control stays under admin/billing.
# Repo truth shows no frontend or internal-job callers for these HTTP routes;
# internal jobs call the billing/report services directly. Keep these routes frozen
# as compatibility tails and do not remove or hand off without external consumer diagnosis.
router = APIRouter(
    prefix="/api/v1/reports",
    tags=["reports", "billing"],
)


def _request_ctx_payload(request: Request, *, token: dict | None = None) -> dict[str, object]:
    request_ctx = request_context_from_request(request, token=token)
    return {
        "actor_type": request_ctx.actor_type.value,
        "request_id": request_ctx.request_id,
        "trace_id": request_ctx.trace_id,
        "ip": request_ctx.ip,
        "user_agent": request_ctx.user_agent,
    }


def _log_reports_route_access(
    *,
    event_type: str,
    route: str,
    method: str,
    request: Request,
    query: dict[str, object],
    started_at: float,
    outcome: str,
    token: dict | None = None,
    result: dict[str, object] | None = None,
    error: str | None = None,
    level: str = "info",
) -> None:
    duration_seconds = max(0.0, perf_counter() - started_at)
    reports_route_metrics.mark_request(route, method, outcome, duration_seconds=duration_seconds)

    extra: dict[str, object] = {
        "route": route,
        "method": method,
        "surface_status": "compatibility_tail",
        "outcome": outcome,
        "duration_ms": round(duration_seconds * 1000, 3),
        "query": query,
        "request_ctx": _request_ctx_payload(request, token=token),
    }
    if result is not None:
        extra["result"] = result
    if error is not None:
        extra["error"] = error

    log_method = getattr(logger, level)
    log_method(event_type, extra=extra)


@router.get("/turnover", response_model=TurnoverReportResponse)
def get_turnover_report_endpoint(
    request: Request,
    group_by: GroupBy = Query("client"),
    from_created_at: datetime = Query(..., alias="from"),
    to_created_at: datetime = Query(..., alias="to"),
    client_id: str | None = None,
    card_id: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    db: Session = Depends(get_db),
) -> TurnoverReportResponse:
    """
    Возвращает агрегированный оборот за период по выбранному измерению.
    """
    # Compatibility aggregate read tail only; no repo caller proof beyond tests/docs.
    route = "/api/v1/reports/turnover"
    started_at = perf_counter()
    query = {
        "group_by": group_by,
        "from_created_at": from_created_at.isoformat(),
        "to_created_at": to_created_at.isoformat(),
        "client_id": client_id,
        "card_id": card_id,
        "merchant_id": merchant_id,
        "terminal_id": terminal_id,
    }
    try:
        report = get_turnover_report(
            db,
            group_by=group_by,
            from_created_at=from_created_at,
            to_created_at=to_created_at,
            client_id=client_id,
            card_id=card_id,
            merchant_id=merchant_id,
            terminal_id=terminal_id,
        )
    except Exception as exc:
        _log_reports_route_access(
            event_type="reports_turnover_failed",
            route=route,
            method="GET",
            request=request,
            query=query,
            started_at=started_at,
            outcome="error",
            error=str(exc),
            level="exception",
        )
        raise

    _log_reports_route_access(
        event_type="reports_turnover_read",
        route=route,
        method="GET",
        request=request,
        query=query,
        started_at=started_at,
        outcome="success",
        result={"items": len(report.items)},
    )
    return report


@router.get("/billing/daily", response_model=list[BillingDailyReportItem])
def get_daily_billing_report(
    request: Request,
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[BillingDailyReportItem]:
    # Compatibility aggregate read over operations, not canonical billing-summary ownership.
    route = "/api/v1/reports/billing/daily"
    started_at = perf_counter()
    query = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "merchant_id": merchant_id,
    }
    try:
        statement = (
            db.query(
                func.date(Operation.created_at).label("op_date"),
                Operation.merchant_id,
                func.coalesce(func.sum(Operation.amount), 0).label("total_amount"),
                func.count().label("total_operations"),
            )
            .filter(Operation.operation_type == "CAPTURE")
            .filter(Operation.created_at >= datetime.combine(date_from, datetime.min.time()))
            .filter(Operation.created_at <= datetime.combine(date_to, datetime.max.time()))
        )

        if merchant_id:
            statement = statement.filter(Operation.merchant_id == merchant_id)

        statement = statement.group_by("op_date", Operation.merchant_id).order_by("op_date")
        rows = statement.all()

        response = [
            BillingDailyReportItem(
                date=row.op_date,
                merchant_id=row.merchant_id,
                total_captured_amount=int(row.total_amount or 0),
                total_operations=row.total_operations,
            )
            for row in rows
        ]
    except Exception as exc:
        _log_reports_route_access(
            event_type="reports_billing_daily_failed",
            route=route,
            method="GET",
            request=request,
            query=query,
            started_at=started_at,
            outcome="error",
            error=str(exc),
            level="exception",
        )
        raise

    _log_reports_route_access(
        event_type="reports_billing_daily_read",
        route=route,
        method="GET",
        request=request,
        query=query,
        started_at=started_at,
        outcome="success",
        result={"items": len(response)},
    )
    return response


@router.post(
    "/billing/summary/rebuild",
    response_model=list[BillingSummaryItem],
    summary="Пересчитать агрегаты биллинга за период",
)
def rebuild_billing_summary(
    request: Request,
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: str | None = None,
    principal: Principal = Depends(require_permission("admin:billing:*")),
    db: Session = Depends(get_db),
) -> list[BillingSummaryItem]:
    # Admin-gated compatibility trigger retained under /reports until explicit admin route handoff.
    # Internal jobs rebuild billing summaries via service-layer calls, not via this HTTP route.
    route = "/api/v1/reports/billing/summary/rebuild"
    started_at = perf_counter()
    query = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "merchant_id": merchant_id,
    }
    try:
        summaries = build_billing_summary_for_date(
            db, date_from=date_from, date_to=date_to, merchant_id=merchant_id
        )
    except BillingPeriodConflict as exc:
        _log_reports_route_access(
            event_type="reports_billing_summary_rebuild_conflict",
            route=route,
            method="POST",
            request=request,
            query=query,
            started_at=started_at,
            outcome="conflict",
            token=principal.raw_claims,
            error=str(exc),
            level="warning",
        )
        AuditService(db).audit(
            event_type="BILLING_SUMMARY_REBUILD_CONFLICT",
            entity_type="billing_summary",
            entity_id=None,
            action="REBUILD_DENIED",
            reason=str(exc),
            request_ctx=request_context_from_request(request),
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        _log_reports_route_access(
            event_type="reports_billing_summary_rebuild_failed",
            route=route,
            method="POST",
            request=request,
            query=query,
            started_at=started_at,
            outcome="error",
            token=principal.raw_claims,
            error=str(exc),
            level="exception",
        )
        raise

    response = [
        BillingSummaryItem(
            id=item.id,
            date=item.date,
            merchant_id=item.merchant_id,
            total_captured_amount=item.total_captured_amount,
            operations_count=item.operations_count,
            status=item.status,
            generated_at=item.generated_at,
            finalized_at=item.finalized_at,
            hash=item.hash,
        )
        for item in summaries
    ]
    _log_reports_route_access(
        event_type="reports_billing_summary_rebuild",
        route=route,
        method="POST",
        request=request,
        query=query,
        started_at=started_at,
        outcome="success",
        token=principal.raw_claims,
        result={"items": len(response)},
    )
    return response


@router.get(
    "/billing/summary",
    response_model=list[BillingSummaryItem],
    summary="Получить агрегированные суммы CAPTURE",
)
def get_billing_summary(
    request: Request,
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[BillingSummaryItem]:
    # Thin compatibility projection over billing_summary rows; canonical detailed owner is admin/billing.
    # Keep frozen until an external consumer diagnosis proves safe removal or route handoff.
    route = "/api/v1/reports/billing/summary"
    started_at = perf_counter()
    query = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "merchant_id": merchant_id,
    }
    try:
        summaries = list_billing_summaries(
            db, date_from=date_from, date_to=date_to, merchant_id=merchant_id
        )

        response = [
            BillingSummaryItem(
                id=item.id,
                date=item.date,
                merchant_id=item.merchant_id,
                total_captured_amount=item.total_captured_amount,
                operations_count=item.operations_count,
                status=item.status,
                generated_at=item.generated_at,
                finalized_at=item.finalized_at,
                hash=item.hash,
            )
            for item in summaries
        ]
    except Exception as exc:
        _log_reports_route_access(
            event_type="reports_billing_summary_failed",
            route=route,
            method="GET",
            request=request,
            query=query,
            started_at=started_at,
            outcome="error",
            error=str(exc),
            level="exception",
        )
        raise

    _log_reports_route_access(
        event_type="reports_billing_summary_read",
        route=route,
        method="GET",
        request=request,
        query=query,
        started_at=started_at,
        outcome="success",
        result={"items": len(response)},
    )
    return response


@router.get("/turnover/export")
def export_turnover_csv_endpoint(
    request: Request,
    group_by: GroupBy = Query("client"),
    from_created_at: datetime = Query(..., alias="from"),
    to_created_at: datetime = Query(..., alias="to"),
    client_id: str | None = None,
    card_id: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    db: Session = Depends(get_db),
):
    # Compatibility export surface over turnover aggregates, not a canonical billing owner API.
    # Repo truth shows no frontend/internal-job caller proof for this HTTP path.
    route = "/api/v1/reports/turnover/export"
    started_at = perf_counter()
    query = {
        "group_by": group_by,
        "from_created_at": from_created_at.isoformat(),
        "to_created_at": to_created_at.isoformat(),
        "client_id": client_id,
        "card_id": card_id,
        "merchant_id": merchant_id,
        "terminal_id": terminal_id,
    }
    try:
        report = get_turnover_report(
            db,
            group_by=group_by,
            from_created_at=from_created_at,
            to_created_at=to_created_at,
            client_id=client_id,
            card_id=card_id,
            merchant_id=merchant_id,
            terminal_id=terminal_id,
        )

        output = StringIO()
        writer = csv.writer(output, delimiter=";")

        writer.writerow(
            [
                "group_by",
                "client_id",
                "card_id",
                "merchant_id",
                "terminal_id",
                "transaction_count",
                "authorized_amount",
                "captured_amount",
                "refunded_amount",
                "net_turnover",
                "currency",
                "from",
                "to",
            ]
        )

        for item in report.items:
            key = item.group_key
            writer.writerow(
                [
                    report.group_by,
                    key.client_id or "",
                    key.card_id or "",
                    key.merchant_id or "",
                    key.terminal_id or "",
                    item.transaction_count,
                    item.authorized_amount,
                    item.captured_amount,
                    item.refunded_amount,
                    item.net_turnover,
                    item.currency,
                    report.from_created_at.isoformat(),
                    report.to_created_at.isoformat(),
                ]
            )

        output.seek(0)
    except Exception as exc:
        _log_reports_route_access(
            event_type="reports_turnover_export_failed",
            route=route,
            method="GET",
            request=request,
            query=query,
            started_at=started_at,
            outcome="error",
            error=str(exc),
            level="exception",
        )
        raise

    _log_reports_route_access(
        event_type="reports_turnover_export",
        route=route,
        method="GET",
        request=request,
        query=query,
        started_at=started_at,
        outcome="success",
        result={"items": len(report.items)},
    )

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="turnover_report.csv"'},
    )
