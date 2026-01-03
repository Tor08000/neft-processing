from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_orders import MarketplaceOrder
from app.schemas.marketplace.analytics import (
    AnalyticsSummaryOut,
    ClientAnalyticsOut,
    ConversionAnalyticsOut,
    ProductAnalyticsOut,
    ProductAnalyticsResponse,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.marketplace_analytics_service import MarketplaceAnalyticsService

router = APIRouter(prefix="/partner/marketplace/analytics", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


def _resolve_period(
    *,
    period: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> tuple[str, datetime | None, datetime | None]:
    if date_from or date_to:
        return "custom", date_from, date_to
    now = datetime.now(timezone.utc)
    if period == "day":
        return "day", now - timedelta(days=1), now
    if period == "week":
        return "week", now - timedelta(days=7), now
    if period == "year":
        return "year", now - timedelta(days=365), now
    return "month", now - timedelta(days=30), now


@router.get("/summary", response_model=AnalyticsSummaryOut)
def get_marketplace_summary(
    period: str | None = Query("month"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> AnalyticsSummaryOut:
    partner_id = _ensure_partner_context(principal)
    resolved_period, date_from, date_to = _resolve_period(period=period, date_from=date_from, date_to=date_to)
    service = MarketplaceAnalyticsService(db)
    summary = service.summary(partner_id=partner_id, date_from=date_from, date_to=date_to)
    return AnalyticsSummaryOut(
        period=resolved_period,
        revenue=summary["revenue"],
        orders=summary["orders"],
        avg_check=summary["avg_check"],
        commission_paid=summary["commission"],
    )


@router.get("/products", response_model=ProductAnalyticsResponse)
def get_marketplace_products(
    period: str | None = Query("month"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> ProductAnalyticsResponse:
    partner_id = _ensure_partner_context(principal)
    _, date_from, date_to = _resolve_period(period=period, date_from=date_from, date_to=date_to)
    service = MarketplaceAnalyticsService(db)
    items = service.product_stats(partner_id=partner_id, date_from=date_from, date_to=date_to)
    return ProductAnalyticsResponse(
        items=[ProductAnalyticsOut(**item) for item in items],
        total=len(items),
    )


@router.get("/clients", response_model=ClientAnalyticsOut)
def get_marketplace_clients(
    period: str | None = Query("month"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> ClientAnalyticsOut:
    partner_id = _ensure_partner_context(principal)
    _, date_from, date_to = _resolve_period(period=period, date_from=date_from, date_to=date_to)
    service = MarketplaceAnalyticsService(db)
    stats = service.client_stats(partner_id=partner_id, date_from=date_from, date_to=date_to)
    return ClientAnalyticsOut(**stats)


@router.get("/conversion", response_model=ConversionAnalyticsOut)
def get_marketplace_conversion(
    period: str | None = Query("month"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> ConversionAnalyticsOut:
    partner_id = _ensure_partner_context(principal)
    _, date_from, date_to = _resolve_period(period=period, date_from=date_from, date_to=date_to)
    service = MarketplaceAnalyticsService(db)
    conversion = service.conversion(partner_id=partner_id, date_from=date_from, date_to=date_to)
    return ConversionAnalyticsOut(
        view_to_order_rate=None,
        order_to_completed_rate=conversion["order_to_completed_rate"],
        created_orders=conversion["created_orders"],
        completed_orders=conversion["completed_orders"],
    )


@router.get("/export")
def export_marketplace_analytics(
    period: str | None = Query("month"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> Response:
    partner_id = _ensure_partner_context(principal)
    _, date_from, date_to = _resolve_period(period=period, date_from=date_from, date_to=date_to)
    query = db.query(MarketplaceOrder).filter(MarketplaceOrder.partner_id == partner_id)
    if date_from:
        query = query.filter(MarketplaceOrder.created_at >= date_from)
    if date_to:
        query = query.filter(MarketplaceOrder.created_at <= date_to)
    orders = query.order_by(MarketplaceOrder.created_at.desc()).all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Marketplace Orders"
    sheet.append(
        [
            "order_id",
            "client_id",
            "product_id",
            "status",
            "quantity",
            "price",
            "discount",
            "final_price",
            "commission",
            "created_at",
            "completed_at",
        ]
    )
    for order in orders:
        sheet.append(
            [
                str(order.id),
                str(order.client_id),
                str(order.product_id),
                str(order.status),
                float(order.quantity),
                float(order.price) if order.price is not None else None,
                float(order.discount) if order.discount is not None else None,
                float(order.final_price) if order.final_price is not None else None,
                float(order.commission) if order.commission is not None else None,
                order.created_at.isoformat() if order.created_at else None,
                order.completed_at.isoformat() if order.completed_at else None,
            ]
        )

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=marketplace_analytics.xlsx"},
    )
