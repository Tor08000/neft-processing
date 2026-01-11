from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.marketplace_catalog import (
    MarketplaceProduct,
    MarketplaceProductModerationStatus,
    MarketplaceProductStatus,
)
from app.models.marketplace_recommendations import (
    MarketplaceEvent,
    MarketplaceEventType,
    OfferCandidate,
    ProductAttributes,
)
from app.models.marketplace_sponsored import (
    MarketplaceSponsoredPlacement,
    SponsoredPlacementStatus,
)
from app.schemas.marketplace.recommendations import MarketplaceEventCreate, RecommendationReason
from app.services.marketplace_catalog_service import MarketplaceCatalogService


_REASON_TEXTS: dict[str, str] = {
    "FUEL_MIX_DIESEL": "Вы часто используете дизель",
    "CATEGORY_AFFINITY_OILS": "Вам интересна категория «Масла»",
    "HIGH_ACTIVITY": "Высокая активность заправок",
    "VIEWED_CATEGORY": "Вы смотрели товары этой категории",
    "POPULAR_IN_SEGMENT": "Популярно среди автопарков вашего типа",
    "MAINTENANCE_SOON": "Похоже, скоро потребуется ТО",
    "CATALOG_FALLBACK": "Популярное в маркетплейсе",
}

_BADGE_TEXTS: dict[str, str] = {
    "MAINTENANCE_SOON": "ТО скоро",
}


class MarketplaceRecommendationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.catalog_service = MarketplaceCatalogService(db)

    def log_event(self, *, tenant_id: str | None, client_id: str, user_id: str | None, payload: MarketplaceEventCreate) -> MarketplaceEvent:
        event = MarketplaceEvent(
            tenant_id=tenant_id,
            client_id=client_id,
            user_id=user_id,
            partner_id=payload.partner_id,
            product_id=payload.product_id,
            event_type=MarketplaceEventType(payload.event_type),
            context=payload.context,
            meta=payload.meta,
            event_ts=datetime.now(timezone.utc),
        )
        self.db.add(event)
        self.db.flush()
        return event

    def list_recommendations(
        self,
        *,
        tenant_id: str | None,
        client_id: str,
        limit: int,
    ) -> list[dict]:
        mode = os.getenv("RECOMMENDER_MODE", "rules").lower()
        if mode == "ml":
            ml_items = self._ml_stub_recommendations(
                tenant_id=tenant_id,
                client_id=client_id,
                limit=limit,
            )
            if ml_items:
                return ml_items
        now = datetime.now(timezone.utc)
        query = self.db.query(OfferCandidate).filter(OfferCandidate.client_id == client_id)
        if tenant_id:
            query = query.filter(OfferCandidate.tenant_id == tenant_id)
        query = query.filter(
            and_(
                or_(OfferCandidate.valid_from.is_(None), OfferCandidate.valid_from <= now),
                or_(OfferCandidate.valid_to.is_(None), OfferCandidate.valid_to >= now),
            )
        )
        candidates = (
            query.order_by(OfferCandidate.base_score.desc(), OfferCandidate.created_at.desc())
            .limit(limit)
            .all()
        )
        if not candidates:
            return self._fallback_recommendations(limit=limit)

        product_ids = [candidate.product_id for candidate in candidates]
        products = (
            self.db.query(MarketplaceProduct)
            .filter(
                MarketplaceProduct.id.in_(product_ids),
                MarketplaceProduct.status == MarketplaceProductStatus.PUBLISHED,
                MarketplaceProduct.moderation_status == MarketplaceProductModerationStatus.APPROVED,
            )
            .all()
        )
        products_by_id = {str(product.id): product for product in products}
        items: list[dict] = []
        placements = self._active_placements(now=now)
        placement_by_product = {str(place.product_id): place for place in placements}
        for candidate in candidates:
            product = products_by_id.get(str(candidate.product_id))
            if not product:
                continue
            price = _price_from_config(product)
            reasons = _normalize_reasons(candidate.reasons)
            badges = ["Рекомендуем"]
            sponsored = False
            placement = placement_by_product.get(str(product.id))
            if placement:
                sponsored = True
                reasons.append(RecommendationReason(code="SPONSORED", text="Sponsored"))
                if "Sponsored" not in badges:
                    badges.append("Sponsored")
            for reason in reasons:
                badge = _BADGE_TEXTS.get(reason.code)
                if badge and badge not in badges:
                    badges.append(badge)
            items.append(
                {
                    "product_id": str(candidate.product_id),
                    "partner_id": str(candidate.partner_id),
                    "title": product.title,
                    "price": price,
                    "discount": None,
                    "final_price": price,
                    "score": Decimal(candidate.base_score or 0),
                    "reasons": reasons,
                    "reason_codes": [reason.code for reason in reasons],
                    "is_sponsored": sponsored,
                    "badges": badges,
                    "valid_to": candidate.valid_to,
                }
            )
        if not items:
            return self._fallback_recommendations(limit=limit)
        return items

    def _fallback_recommendations(self, *, limit: int) -> list[dict]:
        products, _ = self.catalog_service.list_published_products(limit=limit, offset=0)
        items: list[dict] = []
        for product in products:
            price = _price_from_config(product)
            reasons = [RecommendationReason(code="CATALOG_FALLBACK", text=_REASON_TEXTS["CATALOG_FALLBACK"])]
            items.append(
                {
                    "product_id": str(product.id),
                    "partner_id": str(product.partner_id),
                    "title": product.title,
                    "price": price,
                    "discount": None,
                    "final_price": price,
                    "score": Decimal("0"),
                    "reasons": reasons,
                    "reason_codes": [reason.code for reason in reasons],
                    "is_sponsored": False,
                    "badges": ["Рекомендуем"],
                    "valid_to": None,
                }
            )
        return items

    def _ml_stub_recommendations(
        self,
        *,
        tenant_id: str | None,
        client_id: str,
        limit: int,
    ) -> list[dict]:
        return []

    def list_related_products(self, *, product_id: str, limit: int) -> list[MarketplaceProduct]:
        product = self.db.query(MarketplaceProduct).filter(MarketplaceProduct.id == product_id).one_or_none()
        if not product:
            return []
        attributes = self.db.query(ProductAttributes).filter(ProductAttributes.product_id == product_id).one_or_none()
        if attributes:
            related_query = (
                self.db.query(MarketplaceProduct)
                .join(ProductAttributes, ProductAttributes.product_id == MarketplaceProduct.id)
                .filter(
                    MarketplaceProduct.status == MarketplaceProductStatus.PUBLISHED,
                    MarketplaceProduct.moderation_status == MarketplaceProductModerationStatus.APPROVED,
                    ProductAttributes.category_code == attributes.category_code,
                    MarketplaceProduct.id != product_id,
                )
            )
        else:
            related_query = (
                self.db.query(MarketplaceProduct)
                .filter(
                    MarketplaceProduct.status == MarketplaceProductStatus.PUBLISHED,
                    MarketplaceProduct.moderation_status == MarketplaceProductModerationStatus.APPROVED,
                    MarketplaceProduct.category == product.category,
                    MarketplaceProduct.id != product_id,
                )
            )
        return related_query.order_by(MarketplaceProduct.updated_at.desc().nullslast()).limit(limit).all()

    def _active_placements(self, *, now: datetime) -> list[MarketplaceSponsoredPlacement]:
        return (
            self.db.query(MarketplaceSponsoredPlacement)
            .filter(MarketplaceSponsoredPlacement.status == SponsoredPlacementStatus.ACTIVE)
            .filter(MarketplaceSponsoredPlacement.effective_from <= now)
            .filter(
                (MarketplaceSponsoredPlacement.effective_to.is_(None))
                | (MarketplaceSponsoredPlacement.effective_to >= now)
            )
            .filter(MarketplaceSponsoredPlacement.budget_spent < MarketplaceSponsoredPlacement.budget_total)
            .all()
        )


def _normalize_reasons(raw_reasons: Iterable | None) -> list[RecommendationReason]:
    if not raw_reasons:
        return [RecommendationReason(code="CATALOG_FALLBACK", text=_REASON_TEXTS["CATALOG_FALLBACK"])]

    reasons: list[RecommendationReason] = []
    if isinstance(raw_reasons, list):
        for item in raw_reasons:
            if isinstance(item, dict):
                code = str(item.get("code") or "")
                text = str(item.get("text") or _REASON_TEXTS.get(code) or "Рекомендация")
                reasons.append(RecommendationReason(code=code or "UNKNOWN", text=text))
            else:
                code = str(item)
                reasons.append(RecommendationReason(code=code, text=_REASON_TEXTS.get(code, "Рекомендация")))
    else:
        code = str(raw_reasons)
        reasons.append(RecommendationReason(code=code, text=_REASON_TEXTS.get(code, "Рекомендация")))
    if not reasons:
        reasons.append(RecommendationReason(code="CATALOG_FALLBACK", text=_REASON_TEXTS["CATALOG_FALLBACK"]))
    return reasons


def _price_from_config(product: MarketplaceProduct) -> Decimal | None:
    config = product.price_config or {}
    price_model = product.price_model.value if hasattr(product.price_model, "value") else product.price_model
    if price_model == "FIXED":
        amount = config.get("amount")
    elif price_model == "PER_UNIT":
        amount = config.get("amount_per_unit")
    else:
        tiers = config.get("tiers") or []
        amount = tiers[0].get("amount") if tiers else None
    if amount is None:
        return None
    return Decimal(str(amount))
