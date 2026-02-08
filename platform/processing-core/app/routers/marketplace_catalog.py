from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.marketplace.offers import OfferListOut, OfferListResponse, OfferOut
from app.schemas.marketplace.product_cards import ProductCardListOut, ProductCardListResponse, ProductCardOut, ProductMediaOut
from app.schemas.marketplace.services import (
    ServiceAvailabilityResponse,
    ServiceCardListOut,
    ServiceCardListResponse,
)
from app.security.client_auth import require_client_user
from app.services.marketplace_catalog_service import MarketplaceCatalogService
from app.services.marketplace_offers_service import MarketplaceOffersService
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


def _offer_out(offer) -> OfferOut:
    return OfferOut(
        id=str(offer.id),
        partner_id=str(offer.partner_id),
        subject_type=offer.subject_type.value if hasattr(offer.subject_type, "value") else offer.subject_type,
        subject_id=str(offer.subject_id),
        title_override=offer.title_override,
        description_override=offer.description_override,
        status=offer.status.value if hasattr(offer.status, "value") else offer.status,
        moderation_comment=offer.moderation_comment,
        currency=offer.currency,
        price_model=offer.price_model.value if hasattr(offer.price_model, "value") else offer.price_model,
        price_amount=float(offer.price_amount) if offer.price_amount is not None else None,
        price_min=float(offer.price_min) if offer.price_min is not None else None,
        price_max=float(offer.price_max) if offer.price_max is not None else None,
        vat_rate=float(offer.vat_rate) if offer.vat_rate is not None else None,
        terms=offer.terms or {},
        geo_scope=offer.geo_scope.value if hasattr(offer.geo_scope, "value") else offer.geo_scope,
        location_ids=[str(item) for item in (offer.location_ids or [])],
        region_code=offer.region_code,
        entitlement_scope=offer.entitlement_scope.value
        if hasattr(offer.entitlement_scope, "value")
        else offer.entitlement_scope,
        allowed_subscription_codes=[str(code) for code in (offer.allowed_subscription_codes or [])],
        allowed_client_ids=[str(client) for client in (offer.allowed_client_ids or [])],
        valid_from=offer.valid_from,
        valid_to=offer.valid_to,
        created_at=offer.created_at,
        updated_at=offer.updated_at,
    )


def _offer_list_out(offer) -> OfferListOut:
    return OfferListOut(
        id=str(offer.id),
        partner_id=str(offer.partner_id),
        subject_type=offer.subject_type.value if hasattr(offer.subject_type, "value") else offer.subject_type,
        subject_id=str(offer.subject_id),
        title_override=offer.title_override,
        status=offer.status.value if hasattr(offer.status, "value") else offer.status,
        price_model=offer.price_model.value if hasattr(offer.price_model, "value") else offer.price_model,
        currency=offer.currency,
        geo_scope=offer.geo_scope.value if hasattr(offer.geo_scope, "value") else offer.geo_scope,
        entitlement_scope=offer.entitlement_scope.value
        if hasattr(offer.entitlement_scope, "value")
        else offer.entitlement_scope,
        valid_from=offer.valid_from,
        valid_to=offer.valid_to,
    )


def _extract_subscription_codes(token: dict) -> list[str]:
    if not token:
        return []
    codes = token.get("subscription_codes")
    if isinstance(codes, list):
        return [str(item) for item in codes]
    subscription = token.get("subscription") or {}
    code = subscription.get("code") or subscription.get("plan_code")
    if code:
        return [str(code)]
    entitlements = token.get("entitlements_snapshot") or {}
    subscription_payload = entitlements.get("subscription") or {}
    ent_code = subscription_payload.get("code") or subscription_payload.get("plan_code")
    if ent_code:
        return [str(ent_code)]
    return []


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


@router.get("/offers", response_model=OfferListResponse)
def list_active_offers(
    subject_type: str | None = Query(None),
    q: str | None = Query(None),
    geo: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> OfferListResponse:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceOffersService(db)
    items, total = service.list_public_offers(
        subject_type=subject_type,  # type: ignore[arg-type]
        query_text=q,
        geo=geo,
        client_id=str(token.get("client_id")),
        subscription_codes=_extract_subscription_codes(token),
        limit=limit,
        offset=offset,
    )
    return OfferListResponse(
        items=[_offer_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/offers/{offer_id}", response_model=OfferOut)
def get_active_offer(
    offer_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> OfferOut:
    if not token.get("client_id"):
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceOffersService(db)
    offer = service.get_offer(offer_id=offer_id)
    if not offer or not service.is_public_offer(
        offer,
        client_id=str(token.get("client_id")),
        subscription_codes=_extract_subscription_codes(token),
        geo=None,
    ):
        raise HTTPException(status_code=404, detail="offer_not_found")
    return _offer_out(offer)
