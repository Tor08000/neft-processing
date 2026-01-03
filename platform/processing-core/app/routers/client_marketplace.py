from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProductType
from app.schemas.marketplace.catalog import ProductListOut, ProductListResponse, ProductOut
from app.schemas.marketplace.promotions import (
    CouponApplyRequest,
    CouponApplyResponse,
    PromotionListResponse,
    PromotionOut,
)
from app.security.client_auth import require_client_user
from app.services.audit_service import request_context_from_request
from app.services.marketplace_catalog_service import MarketplaceCatalogService
from app.services.marketplace_promotion_service import (
    MarketplacePromotionService,
    MarketplacePromotionServiceError,
)

router = APIRouter(prefix="/client/marketplace", tags=["client-portal-v1"])


def _product_out(product) -> ProductOut:
    return ProductOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        type=product.type.value if hasattr(product.type, "value") else product.type,
        title=product.title,
        description=product.description,
        category=product.category,
        price_model=product.price_model.value if hasattr(product.price_model, "value") else product.price_model,
        price_config=product.price_config,
        status=product.status.value if hasattr(product.status, "value") else product.status,
        published_at=product.published_at,
        archived_at=product.archived_at,
        created_at=product.created_at,
        updated_at=product.updated_at,
        audit_event_id=str(product.audit_event_id) if product.audit_event_id else None,
    )


def _product_list_out(product) -> ProductListOut:
    return ProductListOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        type=product.type.value if hasattr(product.type, "value") else product.type,
        title=product.title,
        category=product.category,
        price_model=product.price_model.value if hasattr(product.price_model, "value") else product.price_model,
        price_config=product.price_config,
        status=product.status.value if hasattr(product.status, "value") else product.status,
        updated_at=product.updated_at,
        published_at=product.published_at,
    )


def _promotion_out(promotion) -> PromotionOut:
    return PromotionOut(
        id=str(promotion.id),
        tenant_id=int(promotion.tenant_id),
        partner_id=str(promotion.partner_id),
        promo_type=promotion.promo_type.value if hasattr(promotion.promo_type, "value") else promotion.promo_type,
        status=promotion.status.value if hasattr(promotion.status, "value") else promotion.status,
        title=promotion.title,
        description=promotion.description,
        scope=promotion.scope,
        eligibility=promotion.eligibility,
        rules=promotion.rules,
        budget=promotion.budget,
        limits=promotion.limits,
        schedule=promotion.schedule,
        created_at=promotion.created_at,
        updated_at=promotion.updated_at,
        audit_event_id=str(promotion.audit_event_id) if promotion.audit_event_id else None,
    )


@router.get("/products", response_model=ProductListResponse)
def list_published_products(
    category: str | None = Query(None),
    q: str | None = Query(None),
    type: MarketplaceProductType | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceCatalogService(db)
    items, total = service.list_published_products(
        product_type=type,
        category=category,
        query_text=q,
        limit=limit,
        offset=offset,
    )
    return ProductListResponse(
        items=[_product_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/products/{product_id}", response_model=ProductOut)
def get_published_product(
    product_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> ProductOut:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceCatalogService(db)
    product = service.get_published_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    return _product_out(product)


@router.get("/deals", response_model=PromotionListResponse)
def list_marketplace_deals(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> PromotionListResponse:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplacePromotionService(db, request_ctx=request_context_from_request(request, token=token))
    items, total = service.list_active_deals(limit=limit, offset=offset)
    return PromotionListResponse(
        items=[_promotion_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/coupons/apply", response_model=CouponApplyResponse)
def apply_coupon_for_quote(
    payload: CouponApplyRequest,
    request: Request,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> CouponApplyResponse:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    catalog_service = MarketplaceCatalogService(db)
    product = catalog_service.get_published_product(product_id=payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    promotion_service = MarketplacePromotionService(db, request_ctx=request_context_from_request(request, token=token))
    try:
        result = promotion_service.evaluate_promotions_for_quote(
            product=product,
            quantity=payload.quantity,
            client_id=str(client_id),
            coupon_code=payload.coupon_code,
        )
    except MarketplacePromotionServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc
    return CouponApplyResponse(
        base_price=result.base_price,
        discount_total=result.discount_total,
        final_price=result.final_price,
        applied_promotions=[str(promo.id) for promo in result.applied_promotions],
        price_snapshot=result.price_snapshot,
    )
