from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProductModerationStatus
from app.schemas.marketplace.catalog import ProductListResponse, ProductOut, ProductModerationRejectRequest
from app.schemas.marketplace.offers import OfferModerationRejectRequest, OfferOut
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_catalog_service import MarketplaceCatalogService
from app.services.marketplace_offers_service import MarketplaceOffersService
from app.routers.admin.marketplace_catalog import _product_list_out, _product_out

router = APIRouter(prefix="/marketplace/moderation", tags=["admin"])


@router.get("/queue", response_model=ProductListResponse)
def list_moderation_queue(
    request: Request,
    status: MarketplaceProductModerationStatus | None = Query(MarketplaceProductModerationStatus.PENDING_REVIEW),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ProductListResponse:
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    items, total = service.list_moderation_queue(status=status, limit=limit, offset=offset)
    return ProductListResponse(
        items=[_product_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{product_id}/approve", response_model=ProductOut)
def approve_product(
    product_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ProductOut:
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    product = service.get_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    try:
        product = service.approve_product(product=product)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _product_out(product)


@router.post("/{product_id}/reject", response_model=ProductOut)
def reject_product(
    product_id: str,
    payload: ProductModerationRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ProductOut:
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    product = service.get_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    try:
        product = service.reject_product(product=product, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _product_out(product)


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


@router.post("/offers/{offer_id}:approve", response_model=OfferOut)
def approve_offer(
    offer_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OfferOut:
    service = MarketplaceOffersService(db)
    offer = service.get_offer(offer_id=offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    try:
        offer = service.approve_offer(offer=offer)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _offer_out(offer)


@router.post("/offers/{offer_id}:reject", response_model=OfferOut)
def reject_offer(
    offer_id: str,
    payload: OfferModerationRejectRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OfferOut:
    service = MarketplaceOffersService(db)
    offer = service.get_offer(offer_id=offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    try:
        offer = service.reject_offer(offer=offer, comment=payload.comment)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _offer_out(offer)
