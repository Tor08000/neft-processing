from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_promotions import MarketplacePromotion, MarketplacePromotionStatus
from app.schemas.marketplace.pricing import DealListResponse, DealPromotionOut
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request

router = APIRouter(prefix="/client/marketplace/deals", tags=["client-portal-v1"])


def _deal_out(promotion) -> DealPromotionOut:
    return DealPromotionOut(
        id=str(promotion.id),
        partner_id=str(promotion.partner_id),
        promo_type=promotion.promo_type.value if hasattr(promotion.promo_type, "value") else promotion.promo_type,
        title=promotion.title,
        description=promotion.description,
        scope_json=promotion.scope_json,
        rules_json=promotion.rules_json,
        schedule_json=promotion.schedule_json,
        created_at=promotion.created_at,
        updated_at=promotion.updated_at,
    )


@router.get("", response_model=DealListResponse)
def list_deals(
    request: Request,
    category: str | None = Query(None),
    partner_id: str | None = Query(None),
    discounted_only: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("client:marketplace:view")),
    db: Session = Depends(get_db),
) -> DealListResponse:
    request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    query = db.query(MarketplacePromotion).filter(MarketplacePromotion.status == MarketplacePromotionStatus.ACTIVE.value)
    if partner_id:
        query = query.filter(MarketplacePromotion.partner_id == partner_id)
    promotions = query.order_by(MarketplacePromotion.created_at.desc()).all()
    items = []
    for promotion in promotions:
        if category:
            scope = promotion.scope_json or {}
            if scope.get("type") != "CATEGORY":
                continue
            if category not in (scope.get("category_codes") or []):
                continue
        items.append(promotion)
    if discounted_only is True:
        items = [item for item in items if item.rules_json]
    total = len(items)
    sliced = items[offset : offset + limit]
    return DealListResponse(
        items=[_deal_out(item) for item in sliced],
        total=total,
        limit=limit,
        offset=offset,
    )
