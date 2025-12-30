from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.bi import bi_user_dep
from app.db import get_db
from app.schemas.bi import (
    BiOfferMetricOut,
    BiPriceInsightOut,
    BiPriceVersionMetricOut,
    BiPriceVersionSeriesPointOut,
)
from app.services.bi import service as bi_service


router = APIRouter(prefix="/api/v1/partner/prices/analytics", tags=["pricing-intelligence"])


def _require_partner(token: dict) -> tuple[int, str]:
    tenant_id = token.get("tenant_id")
    partner_id = token.get("partner_id")
    if tenant_id is None or not partner_id:
        raise HTTPException(status_code=403, detail="missing_partner_context")
    return int(tenant_id), str(partner_id)


@router.get("/versions", response_model=list[BiPriceVersionMetricOut])
def list_price_versions(
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> list[BiPriceVersionMetricOut]:
    tenant_id, partner_id = _require_partner(token)
    metrics = bi_service.list_price_version_metrics(
        db,
        tenant_id=tenant_id,
        partner_id=partner_id,
        date_from=date_from,
        date_to=date_to,
    )
    return [BiPriceVersionMetricOut.model_validate(item) for item in metrics]


@router.get("/versions/series", response_model=list[BiPriceVersionSeriesPointOut])
def list_price_version_series(
    price_version_id: str = Query(...),
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> list[BiPriceVersionSeriesPointOut]:
    tenant_id, partner_id = _require_partner(token)
    series = bi_service.list_price_version_series(
        db,
        tenant_id=tenant_id,
        partner_id=partner_id,
        price_version_id=price_version_id,
        date_from=date_from,
        date_to=date_to,
    )
    return [BiPriceVersionSeriesPointOut.model_validate(item) for item in series]


@router.get("/offers", response_model=list[BiOfferMetricOut])
def list_offers(
    price_version_id: str | None = Query(default=None),
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> list[BiOfferMetricOut]:
    tenant_id, partner_id = _require_partner(token)
    metrics = bi_service.list_offer_metrics(
        db,
        tenant_id=tenant_id,
        partner_id=partner_id,
        date_from=date_from,
        date_to=date_to,
    )
    if price_version_id:
        metrics = metrics
    return [BiOfferMetricOut.model_validate(item) for item in metrics]


@router.get("/insights", response_model=list[BiPriceInsightOut])
def list_insights(
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> list[BiPriceInsightOut]:
    tenant_id, partner_id = _require_partner(token)
    metrics = bi_service.list_price_version_metrics(
        db,
        tenant_id=tenant_id,
        partner_id=partner_id,
        date_from=date_from,
        date_to=date_to,
    )
    insights = bi_service.build_price_insights(metrics, date_from=date_from, date_to=date_to)
    return [BiPriceInsightOut.model_validate(item) for item in insights]


__all__ = ["router"]
