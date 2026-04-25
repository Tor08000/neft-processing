from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProductType, PartnerProfile
from app.models.marketplace_offers import MarketplaceOfferSubjectType
from app.schemas.marketplace.catalog import (
    ProductListOut,
    ProductListResponse,
    ProductOfferListResponse,
    ProductOfferOut,
    ProductOut,
    ProductPartnerOut,
    ProductSlaSummaryOut,
)
from app.schemas.marketplace.recommendations import (
    MarketplaceEventCreate,
    MarketplaceEventOut,
    RecommendationResponse,
    RelatedProductsResponse,
)
from app.schemas.marketplace.sponsored import SponsoredEventCreate, SponsoredEventOut
from app.security.client_auth import require_client_user
from app.services.entitlements_service import assert_module_enabled
from app.services.marketplace_catalog_service import MarketplaceCatalogService
from app.services.marketplace_offers_service import MarketplaceOffersService
from app.services.marketplace_recommendation_service import MarketplaceRecommendationService
from app.services.marketplace_sponsored_service import MarketplaceSponsoredService

router = APIRouter(prefix="/client/marketplace", tags=["client-portal-v1"])


def _require_marketplace_client(token: dict, db: Session) -> str:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    assert_module_enabled(db, client_id=str(client_id), module_code="MARKETPLACE")
    return str(client_id)


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _normalize_text(value: str | None) -> str | None:
    if not value:
        return None
    normalized = " ".join(str(value).split()).strip()
    return normalized or None


def _short_description(value: str | None, *, limit: int = 160) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_amount(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    integer, dot, fraction = text.partition(".")
    sign = ""
    if integer.startswith("-"):
        sign = "-"
        integer = integer[1:]
    chunks: list[str] = []
    while integer:
        chunks.append(integer[-3:])
        integer = integer[:-3]
    grouped = " ".join(reversed(chunks)) if chunks else "0"
    return f"{sign}{grouped}.{fraction}" if dot and fraction else f"{sign}{grouped}"


def _currency_label(currency: str | None) -> str | None:
    if not currency:
        return None
    if currency == "RUB":
        return "₽"
    return currency


def _price_summary(price_model, price_config: dict | None) -> str | None:
    model = _enum_value(price_model)
    if not isinstance(price_config, dict):
        return None
    currency = _currency_label(price_config.get("currency"))
    if model == "FIXED":
        amount = _to_decimal(price_config.get("amount"))
        if amount is None or currency is None:
            return None
        return f"{_format_amount(amount)} {currency}"
    if model == "PER_UNIT":
        amount = _to_decimal(price_config.get("amount_per_unit"))
        if amount is None or currency is None:
            return None
        unit = price_config.get("unit")
        summary = f"{_format_amount(amount)} {currency}"
        return f"{summary} / {unit}" if unit else summary
    if model == "TIERED":
        tiers = price_config.get("tiers")
        if not isinstance(tiers, list) or not tiers or currency is None:
            return None
        amounts = [
            _to_decimal(tier.get("amount"))
            for tier in tiers
            if isinstance(tier, dict) and _to_decimal(tier.get("amount")) is not None
        ]
        if not amounts:
            return None
        return f"{_format_amount(min(amounts))} {currency}+"
    return None


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


def _partner_profiles_by_id(db: Session, partner_ids: list[str]) -> dict[str, PartnerProfile]:
    ids = sorted({partner_id for partner_id in partner_ids if partner_id})
    if not ids:
        return {}
    profiles = db.query(PartnerProfile).filter(PartnerProfile.partner_id.in_(ids)).all()
    return {str(profile.partner_id): profile for profile in profiles}


def _partner_out(*, partner_id, partner_profile: PartnerProfile | None) -> ProductPartnerOut:
    verification_status = _enum_value(partner_profile.verification_status) if partner_profile else None
    return ProductPartnerOut(
        id=str(partner_id),
        company_name=partner_profile.company_name if partner_profile else None,
        verified=verification_status == "VERIFIED" if verification_status is not None else None,
    )


def _product_out(product, *, partner_profile: PartnerProfile | None = None) -> ProductOut:
    return ProductOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        type=_enum_value(product.type),
        title=product.title,
        description=product.description,
        category=product.category,
        price_model=_enum_value(product.price_model),
        price_config=product.price_config,
        price_summary=_price_summary(product.price_model, product.price_config),
        partner=_partner_out(partner_id=product.partner_id, partner_profile=partner_profile),
        sla_summary=ProductSlaSummaryOut(obligations=[], penalties=None),
        status=_enum_value(product.status),
        moderation_status=_enum_value(product.moderation_status),
        moderation_reason=product.moderation_reason,
        moderated_by=str(product.moderated_by) if product.moderated_by else None,
        moderated_at=product.moderated_at,
        published_at=product.published_at,
        archived_at=product.archived_at,
        created_at=product.created_at,
        updated_at=product.updated_at,
        audit_event_id=str(product.audit_event_id) if product.audit_event_id else None,
    )


def _product_offer_out(offer) -> ProductOfferOut:
    return ProductOfferOut(
        id=str(offer.id),
        subject_type=_enum_value(offer.subject_type),
        subject_id=str(offer.subject_id),
        title=offer.title_override,
        currency=offer.currency,
        price_model=_enum_value(offer.price_model),
        price_amount=float(offer.price_amount) if offer.price_amount is not None else None,
        price_min=float(offer.price_min) if offer.price_min is not None else None,
        price_max=float(offer.price_max) if offer.price_max is not None else None,
        geo_scope=_enum_value(offer.geo_scope),
        location_ids=[str(item) for item in (offer.location_ids or [])],
        terms=offer.terms or {},
        valid_from=offer.valid_from,
        valid_to=offer.valid_to,
    )


def _product_list_out(product, *, partner_profile: PartnerProfile | None = None) -> ProductListOut:
    return ProductListOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        type=_enum_value(product.type),
        title=product.title,
        short_description=_short_description(product.description),
        category=product.category,
        price_model=_enum_value(product.price_model),
        price_config=product.price_config,
        price_summary=_price_summary(product.price_model, product.price_config),
        partner_name=partner_profile.company_name if partner_profile else None,
        status=_enum_value(product.status),
        moderation_status=_enum_value(product.moderation_status),
        updated_at=product.updated_at,
        published_at=product.published_at,
        created_at=product.created_at,
        sponsored=False,
        sponsored_badge=None,
        sponsored_campaign_id=None,
    )


def _sponsored_product_out(product, *, sponsored: bool, sponsored_badge: str | None, sponsored_campaign_id: str | None, partner_profile: PartnerProfile | None = None) -> ProductListOut:
    return ProductListOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        type=_enum_value(product.type),
        title=product.title,
        short_description=_short_description(product.description),
        category=product.category,
        price_model=_enum_value(product.price_model),
        price_config=product.price_config,
        price_summary=_price_summary(product.price_model, product.price_config),
        partner_name=partner_profile.company_name if partner_profile else None,
        status=_enum_value(product.status),
        moderation_status=_enum_value(product.moderation_status),
        updated_at=product.updated_at,
        published_at=product.published_at,
        created_at=product.created_at,
        sponsored=sponsored,
        sponsored_badge=sponsored_badge,
        sponsored_campaign_id=sponsored_campaign_id,
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
    placement: str | None = Query("search"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    client_id = _require_marketplace_client(token, db)
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
        client_id=client_id,
        user_id=token.get("user_id"),
    )
    partner_profiles = _partner_profiles_by_id(db, [str(item["product"].partner_id) for item in ranked])
    db.commit()
    return ProductListResponse(
        items=[
            _sponsored_product_out(
                item["product"],
                sponsored=item["sponsored"],
                sponsored_badge=item["sponsored_badge"],
                sponsored_campaign_id=item["sponsored_campaign_id"],
                partner_profile=partner_profiles.get(str(item["product"].partner_id)),
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
    _require_marketplace_client(token, db)
    service = MarketplaceCatalogService(db)
    product = service.get_published_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    partner_profile = _partner_profiles_by_id(db, [str(product.partner_id)]).get(str(product.partner_id))
    return _product_out(product, partner_profile=partner_profile)


@router.get("/products/{product_id}/offers", response_model=ProductOfferListResponse)
def list_published_product_offers(
    product_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> ProductOfferListResponse:
    client_id = _require_marketplace_client(token, db)
    catalog_service = MarketplaceCatalogService(db)
    product = catalog_service.get_published_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    offers_service = MarketplaceOffersService(db)
    subject_type = MarketplaceOfferSubjectType(_enum_value(product.type))
    items, total = offers_service.list_public_offers(
        subject_type=subject_type,
        subject_id=str(product.id),
        client_id=client_id,
        subscription_codes=_extract_subscription_codes(token),
        limit=20,
        offset=0,
    )
    return ProductOfferListResponse(items=[_product_offer_out(item) for item in items], total=total)


# Compatibility/internal shadow only.
# The canonical live client recommendations surface is the dedicated
# `/marketplace/client/recommendations` router in `client.marketplace_recommendations`.
@router.get("/recommendations", response_model=RecommendationResponse)
def list_recommendations(
    limit: int = Query(20, ge=1, le=50),
    placement: str | None = Query(None),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    client_id = _require_marketplace_client(token, db)
    service = MarketplaceRecommendationService(db)
    result = service.list_recommendations(
        tenant_id=token.get("tenant_id"),
        client_id=client_id,
        limit=limit,
    )
    return RecommendationResponse(
        items=result.items,
        generated_at=datetime.now(timezone.utc),
        model=result.model,
        assumptions=result.assumptions,
    )


# Compatibility/internal shadow only.
# The canonical live client events surface is the dedicated batched
# `/marketplace/client/events` router in `marketplace_client_events`.
@router.post("/events", response_model=MarketplaceEventOut, status_code=201)
def record_marketplace_event(
    payload: MarketplaceEventCreate,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> MarketplaceEventOut:
    client_id = _require_marketplace_client(token, db)
    service = MarketplaceRecommendationService(db)
    event = service.log_event(
        tenant_id=token.get("tenant_id"),
        client_id=client_id,
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
    client_id = _require_marketplace_client(token, db)
    service = MarketplaceSponsoredService(db)
    event = service.log_event(
        tenant_id=token.get("tenant_id"),
        client_id=client_id,
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
    _require_marketplace_client(token, db)
    service = MarketplaceRecommendationService(db)
    items = service.list_related_products(product_id=product_id, limit=limit)
    return RelatedProductsResponse(items=[_product_list_out(item) for item in items])
