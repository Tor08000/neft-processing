from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from redis import Redis
from sqlalchemy.orm import Session

from app.models.marketplace_client_events import (
    MarketplaceClientEntityType,
    MarketplaceClientEvent,
    MarketplaceClientEventType,
)
from app.models.marketplace_catalog import MarketplaceProductCard, MarketplaceService
from app.models.marketplace_offers import (
    MarketplaceOffer,
    MarketplaceOfferPriceModel,
    MarketplaceOfferStatus,
    MarketplaceOfferSubjectType,
)
from app.schemas.marketplace.recommendations_v1 import (
    RecommendationItem,
    RecommendationPreview,
    RecommendationPrice,
    RecommendationResponse,
    RecommendationScoreBreakdown,
    RecommendationWhyReason,
)
from app.services.marketplace_offers_service import MarketplaceOffersService

_CACHE_TTL_SECONDS = 300
_CACHE_KEY_TEMPLATE = "mp:reco:v1:{client_id}"
_MEMORY_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}

_REASON_LABELS: dict[str, str] = {
    "RECENT_VIEW": "Похоже на то, что вы смотрели",
    "CATEGORY_AFFINITY": "Часто интересуетесь категорией: {category}",
    "PARTNER_AFFINITY": "Похоже на предложения партнёра, с которым вы работали",
    "SEARCH_MATCH": "Совпадает с вашим поиском",
    "RECENT_PURCHASE": "Вы недавно это покупали",
}


class MarketplaceRecommendationsService:
    def __init__(self, db: Session, *, redis: Redis | None = None) -> None:
        self.db = db
        self.redis = redis
        self.offers_service = MarketplaceOffersService(db)

    def list_recommendations(
        self,
        *,
        tenant_id: int | None,
        client_id: str,
        limit: int,
        subscription_codes: list[str],
        geo: str | None,
    ) -> RecommendationResponse:
        cache_key = _CACHE_KEY_TEMPLATE.format(client_id=client_id)
        cached = self._get_cached(cache_key)
        if cached:
            return self._payload_to_response(cached)

        payload = self._build_recommendations(
            tenant_id=tenant_id,
            client_id=client_id,
            limit=limit,
            subscription_codes=subscription_codes,
            geo=geo,
        )
        self._store_cache(cache_key, payload)
        return self._payload_to_response(payload)

    def explain_why(
        self,
        *,
        tenant_id: int | None,
        client_id: str,
        offer_id: str,
        subscription_codes: list[str],
        geo: str | None,
    ) -> dict[str, Any] | None:
        cache_key = _CACHE_KEY_TEMPLATE.format(client_id=client_id)
        cached = self._get_cached(cache_key)
        if cached:
            why = cached.get("why_by_offer", {}).get(offer_id)
            if why:
                return why

        events_context = self._load_events_context(client_id=client_id)
        offer = (
            self.db.query(MarketplaceOffer)
            .filter(MarketplaceOffer.id == offer_id)
            .one_or_none()
        )
        if not offer:
            return None
        if not self.offers_service.is_public_offer(
            offer,
            client_id=client_id,
            subscription_codes=subscription_codes,
            geo=geo,
        ):
            return None
        _, why_payload = self._score_offer(offer=offer, events_context=events_context)
        return {
            "offer_id": offer_id,
            "reasons": why_payload["reasons"],
            "score_breakdown": why_payload["score_breakdown"],
        }

    def _payload_to_response(self, payload: dict[str, Any]) -> RecommendationResponse:
        return RecommendationResponse(
            items=[RecommendationItem(**item) for item in payload.get("items", [])],
            generated_at=datetime.fromisoformat(payload["generated_at"]),
            ttl_seconds=payload.get("ttl_seconds", _CACHE_TTL_SECONDS),
        )

    def _build_recommendations(
        self,
        *,
        tenant_id: int | None,
        client_id: str,
        limit: int,
        subscription_codes: list[str],
        geo: str | None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        events_context = self._load_events_context(client_id=client_id)

        offers_query = self.db.query(MarketplaceOffer).filter(MarketplaceOffer.status == MarketplaceOfferStatus.ACTIVE)
        offers = offers_query.all()

        scored: list[tuple[MarketplaceOffer, Decimal, dict[str, Any]]] = []
        for offer in offers:
            if not self.offers_service.is_public_offer(
                offer,
                client_id=client_id,
                subscription_codes=subscription_codes,
                geo=geo,
            ):
                continue
            score, why = self._score_offer(offer=offer, events_context=events_context)
            scored.append((offer, score, why))

        scored.sort(key=lambda item: (item[1], item[0].updated_at or item[0].created_at), reverse=True)

        items: list[dict[str, Any]] = []
        why_by_offer: dict[str, dict[str, Any]] = {}
        partner_counts: Counter[str] = Counter()

        for offer, score, why in scored:
            partner_id = str(offer.partner_id)
            if partner_counts[partner_id] >= 6:
                continue
            item = self._offer_to_item(offer=offer, score=score, why_payload=why)
            items.append(item)
            why_by_offer[str(offer.id)] = {
                "offer_id": str(offer.id),
                "reasons": why["reasons"],
                "score_breakdown": why["score_breakdown"],
            }
            partner_counts[partner_id] += 1
            if len(items) >= limit:
                break

        payload = {
            "items": items,
            "generated_at": now.isoformat(),
            "ttl_seconds": _CACHE_TTL_SECONDS,
            "why_by_offer": why_by_offer,
        }
        return payload

    def _load_events_context(self, *, client_id: str) -> dict[str, Any]:
        window_start = datetime.now(timezone.utc) - timedelta(days=7)
        events = (
            self.db.query(MarketplaceClientEvent)
            .filter(MarketplaceClientEvent.client_id == client_id)
            .filter(MarketplaceClientEvent.ts >= window_start)
            .order_by(MarketplaceClientEvent.ts.desc())
            .all()
        )
        views = []
        searches = []
        category_counts: Counter[str] = Counter()
        order_partners: list[str] = []
        recent_purchases: list[dict[str, Any]] = []

        for event in events:
            event_type = event.event_type.value if hasattr(event.event_type, "value") else event.event_type
            payload = event.payload or {}
            if event_type in {
                MarketplaceClientEventType.OFFER_VIEWED.value,
                MarketplaceClientEventType.OFFER_CLICKED.value,
                MarketplaceClientEventType.PRODUCT_VIEWED.value,
                MarketplaceClientEventType.SERVICE_VIEWED.value,
            }:
                views.append(event)
                category = payload.get("category")
                if category:
                    category_counts[str(category)] += 1
            if event_type == MarketplaceClientEventType.SEARCH_PERFORMED.value:
                searches.append(event)
            if event_type == MarketplaceClientEventType.ORDER_PAID.value:
                partner_id = payload.get("partner_id")
                if partner_id:
                    order_partners.append(str(partner_id))
                recent_purchases.append(payload)

        top_category = category_counts.most_common(1)[0][0] if category_counts else None
        return {
            "views": views,
            "searches": searches,
            "top_category": top_category,
            "order_partners": order_partners,
            "recent_purchases": recent_purchases,
        }

    def _score_offer(self, *, offer: MarketplaceOffer, events_context: dict[str, Any]) -> tuple[Decimal, dict[str, Any]]:
        score = Decimal("0")
        reasons: list[RecommendationWhyReason] = []
        breakdown: list[RecommendationScoreBreakdown] = []

        offer_id = str(offer.id)
        subject_id = str(offer.subject_id)
        subject_type = offer.subject_type.value if hasattr(offer.subject_type, "value") else offer.subject_type
        offer_category = self._resolve_offer_category(offer)

        matched_view = self._match_recent_view(
            events_context.get("views", []),
            offer_id=offer_id,
            subject_id=subject_id,
            subject_type=subject_type,
        )
        if matched_view:
            event_type = matched_view.event_type.value if hasattr(matched_view.event_type, "value") else matched_view.event_type
            score += Decimal("5")
            breakdown.append(RecommendationScoreBreakdown(signal="recency_view", value=5))
            reasons.append(
                RecommendationWhyReason(
                    code="RECENT_VIEW",
                    label=_REASON_LABELS["RECENT_VIEW"],
                    evidence={
                        "event_type": event_type,
                        "ts": matched_view.ts.isoformat(),
                    },
                )
            )

        top_category = events_context.get("top_category")
        if offer_category and top_category and offer_category == top_category:
            score += Decimal("3")
            breakdown.append(RecommendationScoreBreakdown(signal="category_affinity", value=3))
            reasons.append(
                RecommendationWhyReason(
                    code="CATEGORY_AFFINITY",
                    label=_REASON_LABELS["CATEGORY_AFFINITY"].format(category=offer_category),
                    evidence={"category": offer_category},
                )
            )

        order_partners = events_context.get("order_partners", [])
        if order_partners and str(offer.partner_id) in order_partners:
            score += Decimal("2")
            breakdown.append(RecommendationScoreBreakdown(signal="partner_affinity", value=2))
            reasons.append(
                RecommendationWhyReason(
                    code="PARTNER_AFFINITY",
                    label=_REASON_LABELS["PARTNER_AFFINITY"],
                    evidence={"partner_id": str(offer.partner_id)},
                )
            )

        matched_search = self._match_search(events_context.get("searches", []), offer=offer)
        if matched_search:
            score += Decimal("1")
            breakdown.append(RecommendationScoreBreakdown(signal="search_match", value=1))
            reasons.append(
                RecommendationWhyReason(
                    code="SEARCH_MATCH",
                    label=_REASON_LABELS["SEARCH_MATCH"],
                    evidence={"q": matched_search},
                )
            )

        if self._is_recent_purchase(events_context.get("recent_purchases", []), offer=offer):
            score += Decimal("-3")
            breakdown.append(RecommendationScoreBreakdown(signal="recent_purchase", value=-3))
            reasons.append(
                RecommendationWhyReason(
                    code="RECENT_PURCHASE",
                    label=_REASON_LABELS["RECENT_PURCHASE"],
                    evidence={"offer_id": offer_id},
                )
            )

        if not reasons:
            reasons.append(RecommendationWhyReason(code="CATALOG_FALLBACK", label="Популярное в маркетплейсе"))

        return score, {"reasons": [reason.dict() for reason in reasons], "score_breakdown": [item.dict() for item in breakdown]}

    def _match_recent_view(
        self,
        events: list[MarketplaceClientEvent],
        *,
        offer_id: str,
        subject_id: str,
        subject_type: str,
    ) -> MarketplaceClientEvent | None:
        for event in events:
            event_type = event.event_type.value if hasattr(event.event_type, "value") else event.event_type
            if event_type not in {
                MarketplaceClientEventType.OFFER_VIEWED.value,
                MarketplaceClientEventType.OFFER_CLICKED.value,
            }:
                continue
            entity_type = event.entity_type.value if hasattr(event.entity_type, "value") else event.entity_type
            entity_id = str(event.entity_id) if event.entity_id else None
            if entity_type == MarketplaceClientEntityType.OFFER.value and entity_id == offer_id:
                return event
            if subject_type == MarketplaceOfferSubjectType.PRODUCT.value and entity_type == MarketplaceClientEntityType.PRODUCT.value:
                if entity_id == subject_id:
                    return event
            if subject_type == MarketplaceOfferSubjectType.SERVICE.value and entity_type == MarketplaceClientEntityType.SERVICE.value:
                if entity_id == subject_id:
                    return event
        return None

    def _match_search(self, events: list[MarketplaceClientEvent], *, offer: MarketplaceOffer) -> str | None:
        title, description = self._resolve_offer_text(offer)
        haystack = f"{title} {description}".lower()
        for event in events:
            payload = event.payload or {}
            query = str(payload.get("q") or "").strip()
            if not query:
                continue
            for token in {item.lower() for item in query.split() if len(item) > 2}:
                if token in haystack:
                    return query[:120]
        return None

    def _is_recent_purchase(self, purchases: list[dict[str, Any]], *, offer: MarketplaceOffer) -> bool:
        offer_id = str(offer.id)
        subject_id = str(offer.subject_id)
        subject_type = offer.subject_type.value if hasattr(offer.subject_type, "value") else offer.subject_type
        for payload in purchases:
            if str(payload.get("offer_id") or "") == offer_id:
                return True
            if str(payload.get("subject_id") or "") == subject_id and payload.get("subject_type") == subject_type:
                return True
        return False

    def _offer_to_item(self, *, offer: MarketplaceOffer, score: Decimal, why_payload: dict[str, Any]) -> dict[str, Any]:
        title, description = self._resolve_offer_text(offer)
        category = self._resolve_offer_category(offer)
        price = self._resolve_offer_price(offer)
        reason_hint = self._resolve_reason_hint(why_payload, category=category)
        preview = RecommendationPreview(short=description[:140] if description else None).dict()
        price_payload = json.loads(price.json()) if price else None
        return {
            "offer_id": str(offer.id),
            "title": title,
            "subject_type": offer.subject_type.value if hasattr(offer.subject_type, "value") else offer.subject_type,
            "price": price_payload,
            "partner_id": str(offer.partner_id),
            "category": category,
            "preview": preview,
            "reason_hint": reason_hint,
        }

    def _resolve_offer_text(self, offer: MarketplaceOffer) -> tuple[str, str]:
        title = offer.title_override
        description = offer.description_override
        subject_type = offer.subject_type.value if hasattr(offer.subject_type, "value") else offer.subject_type
        if subject_type == MarketplaceOfferSubjectType.PRODUCT.value:
            product = self.db.query(MarketplaceProductCard).filter(MarketplaceProductCard.id == offer.subject_id).one_or_none()
            if product:
                title = title or product.title
                description = description or product.description
        if subject_type == MarketplaceOfferSubjectType.SERVICE.value:
            service = self.db.query(MarketplaceService).filter(MarketplaceService.id == offer.subject_id).one_or_none()
            if service:
                title = title or service.title
                description = description or service.description
        return title or "Предложение", description or ""

    def _resolve_offer_category(self, offer: MarketplaceOffer) -> str | None:
        subject_type = offer.subject_type.value if hasattr(offer.subject_type, "value") else offer.subject_type
        if subject_type == MarketplaceOfferSubjectType.PRODUCT.value:
            product = self.db.query(MarketplaceProductCard).filter(MarketplaceProductCard.id == offer.subject_id).one_or_none()
            return product.category if product else None
        if subject_type == MarketplaceOfferSubjectType.SERVICE.value:
            service = self.db.query(MarketplaceService).filter(MarketplaceService.id == offer.subject_id).one_or_none()
            return service.category if service else None
        return None

    def _resolve_offer_price(self, offer: MarketplaceOffer) -> RecommendationPrice | None:
        price_model = offer.price_model.value if hasattr(offer.price_model, "value") else offer.price_model
        amount: Decimal | None
        if price_model == MarketplaceOfferPriceModel.FIXED.value:
            amount = Decimal(offer.price_amount) if offer.price_amount is not None else None
        elif price_model == MarketplaceOfferPriceModel.RANGE.value:
            amount = Decimal(offer.price_min) if offer.price_min is not None else None
        else:
            amount = Decimal(offer.price_amount) if offer.price_amount is not None else None
        return RecommendationPrice(currency=offer.currency, model=price_model, amount=amount)

    def _resolve_reason_hint(self, why_payload: dict[str, Any], *, category: str | None) -> str | None:
        reasons = why_payload.get("reasons", [])
        if not reasons:
            return None
        code = reasons[0].get("code")
        label = _REASON_LABELS.get(code)
        if label and "{category}" in label:
            return label.format(category=category or "")
        return label or reasons[0].get("label")

    def _get_cached(self, cache_key: str) -> dict[str, Any] | None:
        if cache_key in _MEMORY_CACHE:
            expires_at, payload = _MEMORY_CACHE[cache_key]
            if expires_at > datetime.now(timezone.utc):
                return payload
            _MEMORY_CACHE.pop(cache_key, None)
        if not self.redis:
            return None
        try:
            raw = self.redis.get(cache_key)
        except Exception:
            return None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _store_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_CACHE_TTL_SECONDS)
        _MEMORY_CACHE[cache_key] = (expires_at, payload)
        if not self.redis:
            return
        try:
            self.redis.setex(cache_key, _CACHE_TTL_SECONDS, json.dumps(payload))
        except Exception:
            return
