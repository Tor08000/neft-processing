from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.marketplace.product_cards import ProductCardListOut, ProductCardListResponse, ProductCardOut, ProductMediaOut
from app.schemas.marketplace.services import (
    ServiceAvailabilityResponse,
    ServiceCardListOut,
    ServiceCardListResponse,
)
from app.security.client_auth import require_client_user
from app.services.marketplace_catalog_service import MarketplaceCatalogService
from app.services.marketplace_services_service import MarketplaceServicesService

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


def _service_list_out(service) -> ServiceCardListOut:
    return ServiceCardListOut(
        id=str(service.id),
        partner_id=str(service.partner_id),
        title=service.title,
        category=service.category,
        status=service.status.value if hasattr(service.status, "value") else service.status,
        duration_min=service.duration_min,
        updated_at=service.updated_at,
        created_at=service.created_at,
    )


@router.get("/services", response_model=ServiceCardListResponse)
def list_active_services(
    category: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> ServiceCardListResponse:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceServicesService(db)
    items, total = service.list_active_services(
        category=category,
        query_text=q,
        limit=limit,
        offset=offset,
    )
    return ServiceCardListResponse(
        items=[_service_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/services/{service_id}/availability", response_model=ServiceAvailabilityResponse)
def get_active_service_availability(
    service_id: str,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> ServiceAvailabilityResponse:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    status_value = card.status.value if card and hasattr(card.status, "value") else (card.status if card else None)
    if not card or status_value != "ACTIVE":
        raise HTTPException(status_code=404, detail="service_not_found")
    locations = service.list_service_locations(service_id=service_id)
    if date_from:
        parsed_from = date.fromisoformat(date_from)
    else:
        parsed_from = date.today()
    if date_to:
        parsed_to = date.fromisoformat(date_to)
    else:
        parsed_to = parsed_from
    items = service.generate_availability(
        service=card,
        locations=locations,
        date_from=parsed_from,
        date_to=parsed_to,
        public_only=True,
    )
    return ServiceAvailabilityResponse(items=items)
