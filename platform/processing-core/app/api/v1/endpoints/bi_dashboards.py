from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.bi import bi_user_dep
from app.db import get_db
from app.models.bi import BiScopeType
from app.schemas.bi_dashboards import (
    BiDashboardMeta,
    CfoCashflowResponse,
    CfoOverviewResponse,
    ClientAnalyticsDailyMetricsResponse,
    ClientAnalyticsDeclinesResponse,
    ClientAnalyticsDocumentsSummaryResponse,
    ClientAnalyticsExportCreateRequest,
    ClientAnalyticsExportDownloadResponse,
    ClientAnalyticsExportJobResponse,
    ClientAnalyticsExportsSummaryResponse,
    ClientAnalyticsOrdersSummaryResponse,
    ClientAnalyticsSpendSummaryResponse,
    ClientSpendResponse,
    OpsSlaResponse,
    PartnerPerformanceResponse,
)
from app.services.bi import dashboards as bi_dashboards
from app.services.token_claims import DEFAULT_TENANT_ID, resolve_token_tenant_id


router = APIRouter(prefix="/bi", tags=["bi-dashboards"])



def _enforce_scope(token: dict, *, client_id: str | None, partner_id: str | None) -> None:
    token_client = token.get("client_id")
    if token_client and client_id and token_client != client_id:
        raise HTTPException(status_code=403, detail="forbidden_client_scope")

    token_partner = token.get("partner_id")
    if token_partner and partner_id and token_partner != partner_id:
        raise HTTPException(status_code=403, detail="forbidden_partner_scope")



def _require_admin_or_role(token: dict, required: set[str]) -> None:
    roles = bi_dashboards._normalize_roles(token)
    if "ADMIN" in roles:
        return
    bi_dashboards._require_role(token, required)


def _resolve_bi_tenant_id(token: dict, db: Session, *, client_id: str | None = None) -> int:
    return resolve_token_tenant_id(token, db=db, client_id=client_id, default=DEFAULT_TENANT_ID)



_CLIENT_EXPORT_DATASET_SPEND = "spend"
_CLIENT_EXPORT_FORMAT_CSV = "CSV"
_CLIENT_EXPORT_STATUS_DELIVERED = "DELIVERED"


def _require_client_context(token: dict, db: Session) -> tuple[int, str]:
    resolved_client = token.get("client_id")
    if not resolved_client:
        raise HTTPException(status_code=403, detail="forbidden_client_scope")
    _enforce_scope(token, client_id=str(resolved_client), partner_id=None)
    return _resolve_bi_tenant_id(token, db, client_id=str(resolved_client)), str(resolved_client)


def _encode_client_export_job(payload: dict[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def _decode_client_export_job(export_id: str) -> dict[str, Any]:
    try:
        padded = export_id + "=" * (-len(export_id) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="export_not_found") from exc
    required = {"dataset", "tenant_id", "client_id", "from", "to", "created_at", "format", "status"}
    if not required.issubset(set(payload.keys())):
        raise HTTPException(status_code=404, detail="export_not_found")
    return payload


def _serialize_client_export_job(export_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": export_id,
        "dataset": payload["dataset"],
        "status": payload["status"],
        "format": payload["format"],
        "created_at": datetime.fromisoformat(str(payload["created_at"])),
        "ready": str(payload["status"]).upper() == _CLIENT_EXPORT_STATUS_DELIVERED,
        "error_message": payload.get("error_message"),
    }


def _build_client_export_job(*, tenant_id: int, client_id: str, dataset: str, date_from: date, date_to: date) -> tuple[str, dict[str, Any]]:
    payload = {
        "dataset": dataset,
        "tenant_id": tenant_id,
        "client_id": client_id,
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "format": _CLIENT_EXPORT_FORMAT_CSV,
        "status": _CLIENT_EXPORT_STATUS_DELIVERED,
    }
    return _encode_client_export_job(payload), payload


def _resolve_client_export_job(export_id: str, token: dict, db: Session) -> tuple[str, dict[str, Any]]:
    tenant_id, client_id = _require_client_context(token, db)
    payload = _decode_client_export_job(export_id)
    if int(payload["tenant_id"]) != tenant_id or str(payload["client_id"]) != client_id:
        raise HTTPException(status_code=403, detail="forbidden_client_scope")
    return export_id, payload


def _render_client_spend_export_csv(summary: dict[str, Any], *, date_from: date, date_to: date) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["section", "metric", "name", "value"])
    writer.writerow(["meta", "from", "", date_from.isoformat()])
    writer.writerow(["meta", "to", "", date_to.isoformat()])
    writer.writerow(["summary", "total_spend", "", summary.get("total_spend", 0)])
    writer.writerow(["summary", "avg_daily_spend", "", summary.get("avg_daily_spend", 0)])
    for point in summary.get("trend", []):
        writer.writerow(["trend", "value", point.get("date", ""), point.get("value", 0)])
    for item in summary.get("top_stations", []):
        writer.writerow(["top_stations", "amount", item.get("name", ""), item.get("amount", 0)])
    for item in summary.get("top_merchants", []):
        writer.writerow(["top_merchants", "amount", item.get("name", ""), item.get("amount", 0)])
    for item in summary.get("top_cards", []):
        writer.writerow(["top_cards", "amount", item.get("name", ""), item.get("amount", 0)])
    for item in summary.get("top_drivers", []):
        writer.writerow(["top_drivers", "amount", item.get("name", ""), item.get("amount", 0)])
    for item in summary.get("product_breakdown", []):
        writer.writerow(["product_breakdown", "amount", item.get("product", ""), item.get("amount", 0)])
    return buffer.getvalue().encode("utf-8")


@router.get("/metrics/daily", response_model=ClientAnalyticsDailyMetricsResponse)
def client_daily_metrics_endpoint(
    request: Request,
    scope_type: BiScopeType = Query(...),
    scope_id: str = Query(...),
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> ClientAnalyticsDailyMetricsResponse:
    if scope_type == BiScopeType.CLIENT:
        _enforce_scope(token, client_id=scope_id, partner_id=None)
    elif scope_type == BiScopeType.PARTNER:
        _enforce_scope(token, client_id=None, partner_id=scope_id)
    payload, _version = bi_dashboards.client_daily_metrics_summary(
        db,
        tenant_id=_resolve_bi_tenant_id(
            token,
            db,
            client_id=scope_id if scope_type == BiScopeType.CLIENT else None,
        ),
        scope_type=scope_type,
        scope_id=scope_id,
        date_from=date_from,
        date_to=date_to,
        trace_id=request.headers.get("x-trace-id"),
    )
    return ClientAnalyticsDailyMetricsResponse.model_validate(payload)


@router.get("/declines", response_model=ClientAnalyticsDeclinesResponse)
def client_declines_endpoint(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    client_id: str | None = Query(default=None),
    reason: str | None = Query(default=None),
    station_id: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> ClientAnalyticsDeclinesResponse:
    resolved_client = client_id or token.get("client_id")
    if not resolved_client:
        _require_admin_or_role(token, bi_dashboards.CLIENT_ROLES)
    _enforce_scope(token, client_id=resolved_client, partner_id=None)
    payload = bi_dashboards.client_declines_summary(
        db,
        tenant_id=_resolve_bi_tenant_id(token, db, client_id=resolved_client),
        client_id=resolved_client,
        date_from=date_from,
        date_to=date_to,
        reason=reason,
        station_id=station_id,
        trace_id=request.headers.get("x-trace-id"),
    )
    return ClientAnalyticsDeclinesResponse.model_validate(payload)


@router.get("/orders/summary", response_model=ClientAnalyticsOrdersSummaryResponse)
def client_orders_summary_endpoint(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    client_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> ClientAnalyticsOrdersSummaryResponse:
    resolved_client = client_id or token.get("client_id")
    if not resolved_client:
        _require_admin_or_role(token, bi_dashboards.CLIENT_ROLES)
    _enforce_scope(token, client_id=resolved_client, partner_id=None)
    payload = bi_dashboards.client_orders_summary(
        db,
        tenant_id=_resolve_bi_tenant_id(token, db, client_id=resolved_client),
        client_id=resolved_client,
        date_from=date_from,
        date_to=date_to,
        status=status,
        trace_id=request.headers.get("x-trace-id"),
    )
    return ClientAnalyticsOrdersSummaryResponse.model_validate(payload)


@router.get("/documents/summary", response_model=ClientAnalyticsDocumentsSummaryResponse)
def client_documents_summary_endpoint(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    client_id: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> ClientAnalyticsDocumentsSummaryResponse:
    resolved_client = client_id or token.get("client_id")
    if not resolved_client:
        _require_admin_or_role(token, bi_dashboards.CLIENT_ROLES)
    _enforce_scope(token, client_id=resolved_client, partner_id=None)
    payload = bi_dashboards.client_documents_summary(
        db,
        tenant_id=_resolve_bi_tenant_id(token, db, client_id=resolved_client),
        client_id=resolved_client,
        date_from=date_from,
        date_to=date_to,
        trace_id=request.headers.get("x-trace-id"),
    )
    return ClientAnalyticsDocumentsSummaryResponse.model_validate(payload)


@router.get("/exports/summary", response_model=ClientAnalyticsExportsSummaryResponse)
def client_exports_summary_endpoint(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    client_id: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> ClientAnalyticsExportsSummaryResponse:
    resolved_client = client_id or token.get("client_id")
    if not resolved_client:
        _require_admin_or_role(token, bi_dashboards.CLIENT_ROLES)
    _enforce_scope(token, client_id=resolved_client, partner_id=None)
    payload = bi_dashboards.client_exports_summary(
        db,
        tenant_id=_resolve_bi_tenant_id(token, db, client_id=resolved_client),
        client_id=resolved_client,
        date_from=date_from,
        date_to=date_to,
        trace_id=request.headers.get("x-trace-id"),
    )
    return ClientAnalyticsExportsSummaryResponse.model_validate(payload)


@router.get("/spend/summary", response_model=ClientAnalyticsSpendSummaryResponse)
def client_spend_summary_endpoint(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    client_id: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> ClientAnalyticsSpendSummaryResponse:
    resolved_client = client_id or token.get("client_id")
    if not resolved_client:
        _require_admin_or_role(token, bi_dashboards.CLIENT_ROLES)
    _enforce_scope(token, client_id=resolved_client, partner_id=None)
    payload = bi_dashboards.client_spend_summary(
        db,
        tenant_id=_resolve_bi_tenant_id(token, db, client_id=resolved_client),
        client_id=resolved_client,
        date_from=date_from,
        date_to=date_to,
        trace_id=request.headers.get("x-trace-id"),
    )
    return ClientAnalyticsSpendSummaryResponse.model_validate(payload)



@router.post("/exports", response_model=ClientAnalyticsExportJobResponse)
def client_create_export_endpoint(
    payload: ClientAnalyticsExportCreateRequest,
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> ClientAnalyticsExportJobResponse:
    tenant_id, client_id = _require_client_context(token, db)
    if payload.dataset != _CLIENT_EXPORT_DATASET_SPEND:
        raise HTTPException(status_code=400, detail="unsupported_export_dataset")
    export_id, job_payload = _build_client_export_job(
        tenant_id=tenant_id,
        client_id=client_id,
        dataset=payload.dataset,
        date_from=payload.from_,
        date_to=payload.to,
    )
    return ClientAnalyticsExportJobResponse.model_validate(_serialize_client_export_job(export_id, job_payload))


@router.get("/exports/{export_id}", response_model=ClientAnalyticsExportJobResponse)
def client_get_export_endpoint(
    export_id: str,
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> ClientAnalyticsExportJobResponse:
    resolved_export_id, payload = _resolve_client_export_job(export_id, token, db)
    return ClientAnalyticsExportJobResponse.model_validate(_serialize_client_export_job(resolved_export_id, payload))


@router.get("/exports/{export_id}/download", response_model=ClientAnalyticsExportDownloadResponse)
def client_download_export_endpoint(
    export_id: str,
    request: Request,
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> ClientAnalyticsExportDownloadResponse:
    resolved_export_id, payload = _resolve_client_export_job(export_id, token, db)
    if payload["dataset"] != _CLIENT_EXPORT_DATASET_SPEND:
        raise HTTPException(status_code=404, detail="export_not_found")
    summary = bi_dashboards.client_spend_summary(
        db,
        tenant_id=int(payload["tenant_id"]),
        client_id=str(payload["client_id"]),
        date_from=date.fromisoformat(str(payload["from"])),
        date_to=date.fromisoformat(str(payload["to"])),
        trace_id=request.headers.get("x-trace-id"),
    )
    content = _render_client_spend_export_csv(
        summary,
        date_from=date.fromisoformat(str(payload["from"])),
        date_to=date.fromisoformat(str(payload["to"])),
    )
    sha256 = hashlib.sha256(content).hexdigest()
    url = "data:text/csv;charset=utf-8;base64," + base64.b64encode(content).decode("ascii")
    return ClientAnalyticsExportDownloadResponse.model_validate(
        {
            "id": resolved_export_id,
            "status": payload["status"],
            "url": url,
            "sha256": sha256,
        }
    )


@router.get("/cfo/overview", response_model=CfoOverviewResponse)
def cfo_overview_endpoint(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    currency: str = Query("RUB"),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> CfoOverviewResponse:
    _require_admin_or_role(token, bi_dashboards.CFO_ROLES)
    tenant_id = _resolve_bi_tenant_id(token, db)
    totals, series, version = bi_dashboards.cfo_overview(
        db,
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
        trace_id=request.headers.get("x-trace-id"),
    )
    meta = BiDashboardMeta(period_from=date_from, period_to=date_to, currency=currency, mart_version=version)
    return CfoOverviewResponse(totals=totals, series=series, meta=meta)


@router.get("/cfo/cashflow", response_model=CfoCashflowResponse)
def cfo_cashflow_endpoint(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    currency: str = Query("RUB"),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> CfoCashflowResponse:
    _require_admin_or_role(token, bi_dashboards.CFO_ROLES)
    tenant_id = _resolve_bi_tenant_id(token, db)
    totals, series, version = bi_dashboards.cfo_cashflow(
        db,
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
        trace_id=request.headers.get("x-trace-id"),
    )
    meta = BiDashboardMeta(period_from=date_from, period_to=date_to, currency=currency, mart_version=version)
    return CfoCashflowResponse(totals=totals, series=series, meta=meta)


@router.get("/ops/sla", response_model=OpsSlaResponse)
def ops_sla_endpoint(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> OpsSlaResponse:
    _require_admin_or_role(token, bi_dashboards.OPS_ROLES)
    tenant_id = _resolve_bi_tenant_id(token, db)
    totals, series, top_partners, version = bi_dashboards.ops_sla(
        db,
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
        trace_id=request.headers.get("x-trace-id"),
    )
    meta = BiDashboardMeta(period_from=date_from, period_to=date_to, currency="RUB", mart_version=version)
    return OpsSlaResponse(totals=totals, series=series, top_partners_by_breaches=top_partners, meta=meta)


@router.get("/partner/performance", response_model=PartnerPerformanceResponse)
def partner_performance_endpoint(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    partner_id: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> PartnerPerformanceResponse:
    resolved_partner = partner_id or token.get("partner_id")
    if not resolved_partner:
        _require_admin_or_role(token, bi_dashboards.PARTNER_ROLES)
    _enforce_scope(token, client_id=None, partner_id=resolved_partner)
    tenant_id = _resolve_bi_tenant_id(token, db)
    items, version = bi_dashboards.partner_performance(
        db,
        tenant_id=tenant_id,
        partner_id=resolved_partner,
        date_from=date_from,
        date_to=date_to,
        trace_id=request.headers.get("x-trace-id"),
    )
    meta = BiDashboardMeta(period_from=date_from, period_to=date_to, currency="RUB", mart_version=version)
    return PartnerPerformanceResponse(items=items, meta=meta)


@router.get("/client/spend", response_model=ClientSpendResponse)
def client_spend_endpoint(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    client_id: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> ClientSpendResponse:
    resolved_client = client_id or token.get("client_id")
    if not resolved_client:
        _require_admin_or_role(token, bi_dashboards.CLIENT_ROLES)
    _enforce_scope(token, client_id=resolved_client, partner_id=None)
    tenant_id = _resolve_bi_tenant_id(token, db, client_id=resolved_client)
    items, version = bi_dashboards.client_spend(
        db,
        tenant_id=tenant_id,
        client_id=resolved_client,
        date_from=date_from,
        date_to=date_to,
        trace_id=request.headers.get("x-trace-id"),
    )
    meta = BiDashboardMeta(period_from=date_from, period_to=date_to, currency="RUB", mart_version=version)
    return ClientSpendResponse(items=items, meta=meta)


__all__ = ["router"]
