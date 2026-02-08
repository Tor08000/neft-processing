from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.marketplace.product_cards import ProductCardListOut, ProductCardListResponse, ProductCardOut, ProductMediaOut
from app.security.client_auth import require_client_user
from app.services.marketplace_catalog_service import MarketplaceCatalogService

router = APIRouter(prefix="/marketplace/catalog", tags=["marketplace-catalog-v1"])


def _media_out(media) -> ProductMediaOut:
    return ProductMediaOut(
        attachment_id=str(media.attachment_id),
        bucket=media.bucket,
        path=media.path,
        checksum=media.checksum,
        size=media.size,
        mime=media.mime,
        sort_index=media.sort_index,
        created_at=media.created_at,
    )


def _product_out(product, media_items) -> ProductCardOut:
    return ProductCardOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        title=product.title,
        description=product.description,
        category=product.category,
        status=product.status.value if hasattr(product.status, "value") else product.status,
        tags=product.tags or [],
        attributes=product.attributes or {},
        variants=product.variants or [],
        media=[_media_out(item) for item in media_items],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _product_list_out(product) -> ProductCardListOut:
    return ProductCardListOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        title=product.title,
        category=product.category,
        status=product.status.value if hasattr(product.status, "value") else product.status,
        updated_at=product.updated_at,
        created_at=product.created_at,
    )


@router.get("/products", response_model=ProductCardListResponse)
def list_active_products(
    category: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> ProductCardListResponse:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceCatalogService(db)
    items, total = service.list_active_product_cards(
        category=category,
        query_text=q,
        limit=limit,
        offset=offset,
    )
    return ProductCardListResponse(
        items=[_product_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/products/{product_id}", response_model=ProductCardOut)
def get_active_product(
    product_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> ProductCardOut:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceCatalogService(db)
    product = service.get_active_product_card(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    media_items = service.list_product_media(product_id=str(product.id))
    return _product_out(product, media_items)
