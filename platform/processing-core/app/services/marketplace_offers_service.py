from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_catalog import MarketplaceProductCard, MarketplaceService
from app.models.marketplace_offers import (
    MarketplaceOffer,
    MarketplaceOfferEntitlementScope,
    MarketplaceOfferGeoScope,
    MarketplaceOfferStatus,
    MarketplaceOfferSubjectType,
)
from app.schemas.marketplace.offers import assert_editable, assert_transition


class MarketplaceOffersService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_offer(self, *, offer_id: str) -> MarketplaceOffer | None:
        return self.db.query(MarketplaceOffer).filter(MarketplaceOffer.id == offer_id).one_or_none()

    def list_partner_offers(
        self,
        *,
        partner_id: str,
        status: MarketplaceOfferStatus | None = None,
        subject_type: MarketplaceOfferSubjectType | None = None,
        subject_id: str | None = None,
        query_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceOffer], int]:
        query = self.db.query(MarketplaceOffer).filter(MarketplaceOffer.partner_id == partner_id)
        if status:
            query = query.filter(MarketplaceOffer.status == status)
        if subject_type:
            subject_value = subject_type.value if hasattr(subject_type, "value") else subject_type
            query = query.filter(MarketplaceOffer.subject_type == subject_value)
        if subject_id:
            query = query.filter(MarketplaceOffer.subject_id == subject_id)
        if query_text:
            query = query.filter(MarketplaceOffer.title_override.ilike(f"%{query_text}%"))
        total = query.count()
        items = (
            query.order_by(MarketplaceOffer.updated_at.desc().nullslast(), MarketplaceOffer.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def _validate_subject(self, *, partner_id: str, subject_type: MarketplaceOfferSubjectType, subject_id: str) -> None:
        subject_value = subject_type.value if hasattr(subject_type, "value") else subject_type
        if subject_value == MarketplaceOfferSubjectType.PRODUCT.value:
            product = self.db.query(MarketplaceProductCard).filter(MarketplaceProductCard.id == subject_id).one_or_none()
            if not product or str(product.partner_id) != partner_id:
                raise ValueError("product_not_found")
        if subject_value == MarketplaceOfferSubjectType.SERVICE.value:
            service = self.db.query(MarketplaceService).filter(MarketplaceService.id == subject_id).one_or_none()
            if not service or str(service.partner_id) != partner_id:
                raise ValueError("service_not_found")

    def create_offer(self, *, partner_id: str, payload: dict) -> MarketplaceOffer:
        subject_type = payload["subject_type"]
        subject_id = payload["subject_id"]
        self._validate_subject(partner_id=partner_id, subject_type=subject_type, subject_id=subject_id)
        now = datetime.now(timezone.utc)
        offer = MarketplaceOffer(
            id=new_uuid_str(),
            partner_id=partner_id,
            subject_type=subject_type,
            subject_id=subject_id,
            title_override=payload.get("title_override"),
            description_override=payload.get("description_override"),
            status=MarketplaceOfferStatus.DRAFT.value,
            moderation_comment=None,
            currency=payload["currency"],
            price_model=payload["price_model"],
            price_amount=payload.get("price_amount"),
            price_min=payload.get("price_min"),
            price_max=payload.get("price_max"),
            vat_rate=payload.get("vat_rate"),
            terms=payload.get("terms") or {},
            geo_scope=payload["geo_scope"],
            location_ids=payload.get("location_ids") or [],
            region_code=payload.get("region_code"),
            entitlement_scope=payload["entitlement_scope"],
            allowed_subscription_codes=payload.get("allowed_subscription_codes") or [],
            allowed_client_ids=payload.get("allowed_client_ids") or [],
            valid_from=payload.get("valid_from"),
            valid_to=payload.get("valid_to"),
            created_at=now,
            updated_at=now,
        )
        self.db.add(offer)
        self.db.flush()
        return offer

    def update_offer(self, *, offer: MarketplaceOffer, payload: dict) -> MarketplaceOffer:
        assert_editable(offer.status)
        for field in (
            "title_override",
            "description_override",
            "currency",
            "price_model",
            "price_amount",
            "price_min",
            "price_max",
            "vat_rate",
            "terms",
            "geo_scope",
            "location_ids",
            "region_code",
            "entitlement_scope",
            "allowed_subscription_codes",
            "allowed_client_ids",
            "valid_from",
            "valid_to",
        ):
            if field in payload:
                setattr(offer, field, payload[field])
        offer.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return offer

    def submit_offer(self, *, offer: MarketplaceOffer) -> MarketplaceOffer:
        assert_transition(offer.status, MarketplaceOfferStatus.PENDING_REVIEW, actor_role="partner")
        offer.status = MarketplaceOfferStatus.PENDING_REVIEW
        offer.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return offer

    def archive_offer(self, *, offer: MarketplaceOffer) -> MarketplaceOffer:
        assert_transition(offer.status, MarketplaceOfferStatus.ARCHIVED, actor_role="partner")
        offer.status = MarketplaceOfferStatus.ARCHIVED
        offer.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return offer

    def approve_offer(self, *, offer: MarketplaceOffer) -> MarketplaceOffer:
        assert_transition(offer.status, MarketplaceOfferStatus.ACTIVE, actor_role="admin")
        offer.status = MarketplaceOfferStatus.ACTIVE
        offer.moderation_comment = None
        offer.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return offer

    def reject_offer(self, *, offer: MarketplaceOffer, comment: str) -> MarketplaceOffer:
        assert_transition(offer.status, MarketplaceOfferStatus.DRAFT, actor_role="admin")
        offer.status = MarketplaceOfferStatus.DRAFT
        offer.moderation_comment = comment
        offer.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return offer

    def list_public_offers(
        self,
        *,
        subject_type: MarketplaceOfferSubjectType | None = None,
        query_text: str | None = None,
        geo: str | None = None,
        client_id: str | None = None,
        subscription_codes: Iterable[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceOffer], int]:
        now = datetime.now(timezone.utc)
        query = self.db.query(MarketplaceOffer).filter(MarketplaceOffer.status == MarketplaceOfferStatus.ACTIVE)
        query = query.filter(
            and_(
                or_(MarketplaceOffer.valid_from.is_(None), MarketplaceOffer.valid_from <= now),
                or_(MarketplaceOffer.valid_to.is_(None), MarketplaceOffer.valid_to >= now),
            )
        )
        if subject_type:
            subject_value = subject_type.value if hasattr(subject_type, "value") else subject_type
            query = query.filter(MarketplaceOffer.subject_type == subject_value)
        if query_text:
            query = query.filter(MarketplaceOffer.title_override.ilike(f"%{query_text}%"))
        items = query.order_by(MarketplaceOffer.updated_at.desc().nullslast(), MarketplaceOffer.id.desc()).all()
        filtered = [
            offer
            for offer in items
            if self._matches_entitlements(offer, client_id=client_id, subscription_codes=subscription_codes)
            and self._matches_geo(offer, geo=geo)
        ]
        total = len(filtered)
        return filtered[offset : offset + limit], total

    def _matches_entitlements(
        self,
        offer: MarketplaceOffer,
        *,
        client_id: str | None,
        subscription_codes: Iterable[str] | None,
    ) -> bool:
        scope = offer.entitlement_scope
        if hasattr(scope, "value"):
            scope = scope.value
        codes = {str(code) for code in (subscription_codes or [])}
        if scope == MarketplaceOfferEntitlementScope.ALL_CLIENTS.value:
            return True
        if scope == MarketplaceOfferEntitlementScope.SUBSCRIPTION_ONLY.value:
            allowed = {str(code) for code in (offer.allowed_subscription_codes or [])}
            return bool(codes.intersection(allowed))
        if scope == MarketplaceOfferEntitlementScope.SEGMENT_ONLY.value:
            if not client_id:
                return False
            allowed = {str(client) for client in (offer.allowed_client_ids or [])}
            return client_id in allowed
        return False

    def _matches_geo(self, offer: MarketplaceOffer, *, geo: str | None) -> bool:
        if not geo:
            return True
        scope = offer.geo_scope
        if hasattr(scope, "value"):
            scope = scope.value
        if scope == MarketplaceOfferGeoScope.ALL_PARTNER_LOCATIONS.value:
            return True
        if scope == MarketplaceOfferGeoScope.SELECTED_LOCATIONS.value:
            return geo in {str(item) for item in (offer.location_ids or [])}
        if scope == MarketplaceOfferGeoScope.REGION.value:
            return offer.region_code == geo
        return False

    def is_public_offer(
        self,
        offer: MarketplaceOffer,
        *,
        client_id: str | None,
        subscription_codes: Iterable[str] | None,
        geo: str | None,
    ) -> bool:
        status_value = offer.status.value if hasattr(offer.status, "value") else offer.status
        if status_value != MarketplaceOfferStatus.ACTIVE.value:
            return False
        now = datetime.now(timezone.utc)
        if offer.valid_from and offer.valid_from > now:
            return False
        if offer.valid_to and offer.valid_to < now:
            return False
        return self._matches_entitlements(offer, client_id=client_id, subscription_codes=subscription_codes) and self._matches_geo(
            offer, geo=geo
        )
