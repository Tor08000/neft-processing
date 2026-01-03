from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProductType
from app.schemas.marketplace.catalog import ProductListOut, ProductListResponse, ProductOut
from app.schemas.marketplace.recommendations import (
    MarketplaceEventCreate,
    MarketplaceEventOut,
    RecommendationResponse,
    RelatedProductsResponse,
)
from app.schemas.marketplace.sponsored import SponsoredEventCreate, SponsoredEventOut
from app.security.client_auth import require_client_user
from app.services.marketplace_catalog_service import MarketplaceCatalogService
from app.services.marketplace_recommendation_service import MarketplaceRecommendationService
from app.services.marketplace_sponsored_service import MarketplaceSponsoredService

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
        sponsored=False,
        sponsored_badge=None,
        sponsored_campaign_id=None,
    )


def _sponsored_product_out(product, *, sponsored: bool, sponsored_badge: str | None, sponsored_campaign_id: str | None) -> ProductListOut:
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
        sponsored=sponsored,
        sponsored_badge=sponsored_badge,
        sponsored_campaign_id=sponsored_campaign_id,
    )


@router.get("/products", response_model=ProductListResponse)
def list_published_products(
    category: str | None = Query(None),
    q: str | None = Query(None),
    type: MarketplaceProductType | None = Query(None),
    placement: str | None = Query("search"),
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
    sponsored_service = MarketplaceSponsoredService(db)
    ranked = sponsored_service.apply_sponsored_ranking(
        products=items,
        tenant_id=token.get("tenant_id"),
        placement=placement,
        category=category,
        context={"placement": placement, "query": q},
        client_id=token.get("client_id"),
        user_id=token.get("user_id"),
    )
    db.commit()
    return ProductListResponse(
        items=[
            _sponsored_product_out(
                item["product"],
                sponsored=item["sponsored"],
                sponsored_badge=item["sponsored_badge"],
                sponsored_campaign_id=item["sponsored_campaign_id"],
            )
            for item in ranked
        ],
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


@router.get("/recommendations", response_model=RecommendationResponse)
def list_recommendations(
    limit: int = Query(20, ge=1, le=50),
    placement: str | None = Query(None),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceRecommendationService(db)
    items = service.list_recommendations(
        tenant_id=token.get("tenant_id"),
        client_id=token["client_id"],
        limit=limit,
    )
    return RecommendationResponse(
        items=items,
        generated_at=datetime.now(timezone.utc),
        model="offer_engine_v1",
    )


@router.post("/events", response_model=MarketplaceEventOut, status_code=201)
def record_marketplace_event(
    payload: MarketplaceEventCreate,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> MarketplaceEventOut:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceRecommendationService(db)
    event = service.log_event(
        tenant_id=token.get("tenant_id"),
        client_id=token["client_id"],
        user_id=token.get("user_id"),
        payload=payload,
    )
    return MarketplaceEventOut(
        id=str(event.id),
        client_id=str(event.client_id),
        user_id=str(event.user_id) if event.user_id else None,
        partner_id=str(event.partner_id) if event.partner_id else None,
        product_id=str(event.product_id) if event.product_id else None,
        event_type=event.event_type.value if hasattr(event.event_type, "value") else event.event_type,
        event_ts=event.event_ts,
        context=event.context,
        meta=event.meta,
    )


@router.post("/sponsored/events", response_model=SponsoredEventOut, status_code=201)
def record_sponsored_event(
    payload: SponsoredEventCreate,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> SponsoredEventOut:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceSponsoredService(db)
    event = service.log_event(
        tenant_id=token.get("tenant_id"),
        client_id=token.get("client_id"),
        user_id=token.get("user_id"),
        payload=payload.dict(),
    )
    db.commit()
    return SponsoredEventOut(
        id=str(event.id),
        campaign_id=str(event.campaign_id),
        partner_id=str(event.partner_id),
        client_id=str(event.client_id) if event.client_id else None,
        user_id=str(event.user_id) if event.user_id else None,
        product_id=str(event.product_id) if event.product_id else None,
        event_type=event.event_type.value if hasattr(event.event_type, "value") else event.event_type,
        event_ts=event.event_ts,
        context=event.context,
        meta=event.meta,
    )


@router.get("/products/{product_id}/related", response_model=RelatedProductsResponse)
def list_related_products(
    product_id: str,
    limit: int = Query(12, ge=1, le=50),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> RelatedProductsResponse:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceRecommendationService(db)
    items = service.list_related_products(product_id=product_id, limit=limit)
    return RelatedProductsResponse(items=[_product_list_out(item) for item in items])
