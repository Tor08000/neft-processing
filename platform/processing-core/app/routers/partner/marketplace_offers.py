from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_offers import MarketplaceOfferStatus, MarketplaceOfferSubjectType
from app.schemas.marketplace.offers import OfferCreate, OfferListOut, OfferListResponse, OfferOut, OfferUpdate
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.marketplace_offers_service import MarketplaceOffersService

router = APIRouter(prefix="/marketplace/partner/offers", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


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


@router.get("", response_model=OfferListResponse)
def list_partner_offers(
    status: MarketplaceOfferStatus | None = Query(None),
    subject_type: MarketplaceOfferSubjectType | None = Query(None),
    subject_id: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> OfferListResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOffersService(db)
    items, total = service.list_partner_offers(
        partner_id=partner_id,
        status=status,
        subject_type=subject_type,
        subject_id=subject_id,
        query_text=q,
        limit=limit,
        offset=offset,
    )
    return OfferListResponse(
        items=[_offer_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{offer_id}", response_model=OfferOut)
def get_partner_offer(
    offer_id: str,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> OfferOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOffersService(db)
    offer = service.get_offer(offer_id=offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    if str(offer.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return _offer_out(offer)


@router.post("", response_model=OfferOut, status_code=status.HTTP_201_CREATED)
def create_partner_offer(
    payload: OfferCreate,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> OfferOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOffersService(db)
    try:
        offer = service.create_offer(partner_id=partner_id, payload=payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    return _offer_out(offer)


@router.patch("/{offer_id}", response_model=OfferOut)
def update_partner_offer(
    offer_id: str,
    payload: OfferUpdate,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> OfferOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOffersService(db)
    offer = service.get_offer(offer_id=offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    if str(offer.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        offer = service.update_offer(offer=offer, payload=payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    return _offer_out(offer)


@router.post("/{offer_id}:submit", response_model=OfferOut)
def submit_partner_offer(
    offer_id: str,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> OfferOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOffersService(db)
    offer = service.get_offer(offer_id=offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    if str(offer.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        offer = service.submit_offer(offer=offer)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    return _offer_out(offer)


@router.post("/{offer_id}:archive", response_model=OfferOut)
def archive_partner_offer(
    offer_id: str,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> OfferOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOffersService(db)
    offer = service.get_offer(offer_id=offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    if str(offer.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        offer = service.archive_offer(offer=offer)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    return _offer_out(offer)
