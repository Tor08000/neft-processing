from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.bi import bi_user_dep
from app.db import get_db
from app.schemas.bi_dashboards import (
    BiDashboardMeta,
    CfoCashflowResponse,
    CfoOverviewResponse,
    ClientSpendResponse,
    OpsSlaResponse,
    PartnerPerformanceResponse,
)
from app.services.bi import dashboards as bi_dashboards


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
    tenant_id = int(token.get("tenant_id"))
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
    tenant_id = int(token.get("tenant_id"))
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
    tenant_id = int(token.get("tenant_id"))
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
    tenant_id = int(token.get("tenant_id"))
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
    tenant_id = int(token.get("tenant_id"))
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
