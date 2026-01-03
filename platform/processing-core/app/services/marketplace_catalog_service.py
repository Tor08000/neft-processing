from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_catalog import (
    MarketplaceProduct,
    MarketplaceProductModerationStatus,
    MarketplaceProductStatus,
    MarketplaceProductType,
    PartnerProfile,
    PartnerVerificationStatus,
)
from app.schemas.marketplace.catalog import validate_price_config
from app.services.audit_service import AuditService, RequestContext
from app.services.decision_memory.records import record_decision_memory


class MarketplaceCatalogService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx
        self.audit_service = AuditService(db)

    def _audit(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        action: str,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ):
        return self.audit_service.audit(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before=before,
            after=after,
            reason=reason,
            request_ctx=self.request_ctx,
        )

    def get_partner_profile(self, *, partner_id: str) -> PartnerProfile | None:
        return self.db.query(PartnerProfile).filter(PartnerProfile.partner_id == partner_id).one_or_none()

    def list_partner_profiles(
        self,
        *,
        verification_status: PartnerVerificationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PartnerProfile], int]:
        query = self.db.query(PartnerProfile)
        if verification_status:
            query = query.filter(PartnerProfile.verification_status == verification_status)
        total = query.count()
        items = (
            query.order_by(PartnerProfile.created_at.desc(), PartnerProfile.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def upsert_partner_profile(
        self,
        *,
        partner_id: str,
        company_name: str,
        description: str | None,
    ) -> PartnerProfile:
        profile = self.get_partner_profile(partner_id=partner_id)
        now = datetime.now(timezone.utc)
        if profile:
            before = {
                "company_name": profile.company_name,
                "description": profile.description,
                "verification_status": profile.verification_status.value,
            }
            profile.company_name = company_name
            profile.description = description
            profile.updated_at = now
            after = {
                "company_name": profile.company_name,
                "description": profile.description,
                "verification_status": profile.verification_status.value,
            }
            audit = self._audit(
                event_type="PARTNER_PROFILE_UPDATED",
                entity_type="partner_profile",
                entity_id=str(profile.id),
                action="PARTNER_PROFILE_UPDATED",
                before=before,
                after=after,
            )
            profile.audit_event_id = audit.id
        else:
            profile_id = new_uuid_str()
            audit = self._audit(
                event_type="PARTNER_PROFILE_CREATED",
                entity_type="partner_profile",
                entity_id=profile_id,
                action="PARTNER_PROFILE_CREATED",
                after={
                    "company_name": company_name,
                    "description": description,
                    "verification_status": PartnerVerificationStatus.PENDING.value,
                },
            )
            profile = PartnerProfile(
                id=profile_id,
                partner_id=partner_id,
                company_name=company_name,
                description=description,
                verification_status=PartnerVerificationStatus.PENDING.value,
                created_at=now,
                updated_at=now,
                audit_event_id=audit.id,
            )
            self.db.add(profile)
        self.db.flush()
        return profile

    def verify_partner(
        self,
        *,
        partner_id: str,
        status: PartnerVerificationStatus,
        reason: str | None = None,
    ) -> PartnerProfile:
        profile = self.get_partner_profile(partner_id=partner_id)
        if not profile:
            raise ValueError("partner_profile_not_found")
        before = {"verification_status": profile.verification_status.value}
        profile.verification_status = status
        profile.updated_at = datetime.now(timezone.utc)
        after = {"verification_status": profile.verification_status.value}
        audit = self._audit(
            event_type="PARTNER_VERIFIED",
            entity_type="partner_profile",
            entity_id=str(profile.id),
            action="PARTNER_VERIFIED",
            before=before,
            after=after,
            reason=reason,
        )
        profile.audit_event_id = audit.id

        record_decision_memory(
            self.db,
            case_id=None,
            decision_type="partner_verified",
            decision_ref_id=str(profile.partner_id),
            decision_at=datetime.now(timezone.utc),
            decided_by_user_id=self.request_ctx.actor_id if self.request_ctx else None,
            context_snapshot={"partner_id": str(profile.partner_id), "status": status.value},
            rationale=reason or "Partner verification status updated",
            score_snapshot=None,
            mastery_snapshot=None,
            audit_event_id=str(audit.id),
        )
        self.db.flush()
        return profile

    def list_partner_products(
        self,
        *,
        partner_id: str,
        status: MarketplaceProductStatus | None = None,
        moderation_status: MarketplaceProductModerationStatus | None = None,
        product_type: MarketplaceProductType | None = None,
        category: str | None = None,
        query_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceProduct], int]:
        query = self.db.query(MarketplaceProduct).filter(MarketplaceProduct.partner_id == partner_id)
        if status:
            query = query.filter(MarketplaceProduct.status == status)
        if moderation_status:
            query = query.filter(MarketplaceProduct.moderation_status == moderation_status)
        if product_type:
            query = query.filter(MarketplaceProduct.type == product_type)
        if category:
            query = query.filter(MarketplaceProduct.category == category)
        if query_text:
            like = f"%{query_text}%"
            query = query.filter(
                or_(
                    MarketplaceProduct.title.ilike(like),
                    MarketplaceProduct.description.ilike(like),
                )
            )
        total = query.count()
        items = (
            query.order_by(MarketplaceProduct.updated_at.desc().nullslast(), MarketplaceProduct.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def create_product(
        self,
        *,
        partner_id: str,
        payload: dict,
    ) -> MarketplaceProduct:
        product_id = new_uuid_str()
        audit = self._audit(
            event_type="PRODUCT_CREATED",
            entity_type="marketplace_product",
            entity_id=product_id,
            action="PRODUCT_CREATED",
            after={
                "partner_id": partner_id,
                "type": payload["type"],
                "title": payload["title"],
                "category": payload["category"],
                "price_model": payload["price_model"],
                "status": MarketplaceProductStatus.DRAFT.value,
                "moderation_status": MarketplaceProductModerationStatus.DRAFT.value,
            },
        )
        product = MarketplaceProduct(
            id=product_id,
            partner_id=partner_id,
            type=payload["type"],
            title=payload["title"],
            description=payload["description"],
            category=payload["category"],
            price_model=payload["price_model"],
            price_config=payload["price_config"],
            status=MarketplaceProductStatus.DRAFT.value,
            moderation_status=MarketplaceProductModerationStatus.DRAFT.value,
            audit_event_id=audit.id,
        )
        self.db.add(product)
        self.db.flush()
        return product

    def update_product(
        self,
        *,
        product: MarketplaceProduct,
        payload: dict,
    ) -> MarketplaceProduct:
        if product.status == MarketplaceProductStatus.ARCHIVED:
            raise ValueError("product_archived")
        if product.moderation_status not in {
            MarketplaceProductModerationStatus.DRAFT,
            MarketplaceProductModerationStatus.REJECTED,
        }:
            raise ValueError("product_not_editable")
        before = {
            "type": product.type.value,
            "title": product.title,
            "description": product.description,
            "category": product.category,
            "price_model": product.price_model.value,
            "price_config": product.price_config,
        }
        price_model = payload.get("price_model")
        price_config = payload.get("price_config")
        if price_config is not None and price_model is None:
            validate_price_config(product.price_model.value, price_config)
        for key in ("type", "title", "description", "category", "price_model", "price_config"):
            if key in payload and payload[key] is not None:
                setattr(product, key, payload[key])
        product.updated_at = datetime.now(timezone.utc)
        after = {
            "type": product.type.value,
            "title": product.title,
            "description": product.description,
            "category": product.category,
            "price_model": product.price_model.value,
            "price_config": product.price_config,
        }
        audit = self._audit(
            event_type="PRODUCT_UPDATED",
            entity_type="marketplace_product",
            entity_id=str(product.id),
            action="PRODUCT_UPDATED",
            before=before,
            after=after,
        )
        product.audit_event_id = audit.id
        self.db.flush()
        return product

    def submit_product_for_review(self, *, product: MarketplaceProduct) -> MarketplaceProduct:
        if product.status == MarketplaceProductStatus.ARCHIVED:
            raise ValueError("product_archived")
        if product.moderation_status not in {
            MarketplaceProductModerationStatus.DRAFT,
            MarketplaceProductModerationStatus.REJECTED,
        }:
            raise ValueError("product_invalid_moderation_state")
        before = {
            "status": product.status.value,
            "moderation_status": product.moderation_status.value,
        }
        product.status = MarketplaceProductStatus.PUBLISHED
        product.moderation_status = MarketplaceProductModerationStatus.PENDING_REVIEW
        product.moderation_reason = None
        product.moderated_by = None
        product.moderated_at = None
        product.published_at = None
        product.updated_at = datetime.now(timezone.utc)
        after = {
            "status": product.status.value,
            "moderation_status": product.moderation_status.value,
        }
        audit = self._audit(
            event_type="PRODUCT_SUBMITTED_FOR_REVIEW",
            entity_type="marketplace_product",
            entity_id=str(product.id),
            action="PRODUCT_SUBMITTED_FOR_REVIEW",
            before=before,
            after=after,
        )
        product.audit_event_id = audit.id
        self.db.flush()
        return product

    def publish_product(self, *, product: MarketplaceProduct) -> MarketplaceProduct:
        return self.submit_product_for_review(product=product)

    def archive_product(self, *, product: MarketplaceProduct) -> MarketplaceProduct:
        if product.status == MarketplaceProductStatus.ARCHIVED:
            raise ValueError("product_already_archived")
        before = {"status": product.status.value}
        product.status = MarketplaceProductStatus.ARCHIVED
        product.archived_at = datetime.now(timezone.utc)
        product.updated_at = product.archived_at
        after = {"status": product.status.value}
        audit = self._audit(
            event_type="PRODUCT_ARCHIVED",
            entity_type="marketplace_product",
            entity_id=str(product.id),
            action="PRODUCT_ARCHIVED",
            before=before,
            after=after,
        )
        product.audit_event_id = audit.id
        self.db.flush()
        return product

    def admin_set_product_status(
        self,
        *,
        product: MarketplaceProduct,
        status: MarketplaceProductStatus,
        reason: str | None = None,
    ) -> MarketplaceProduct:
        before = {"status": product.status.value, "moderation_status": product.moderation_status.value}
        now = datetime.now(timezone.utc)
        product.status = status
        if status == MarketplaceProductStatus.PUBLISHED:
            product.published_at = product.published_at or now
            product.archived_at = None
            product.moderation_status = MarketplaceProductModerationStatus.APPROVED
            product.moderated_at = now
            product.moderated_by = self.request_ctx.actor_id if self.request_ctx else None
            product.moderation_reason = None
        elif status == MarketplaceProductStatus.ARCHIVED:
            product.archived_at = now
        else:
            product.published_at = None
            product.archived_at = None
            product.moderation_status = MarketplaceProductModerationStatus.DRAFT
            product.moderated_at = None
            product.moderated_by = None
            product.moderation_reason = None
        product.updated_at = now
        after = {"status": product.status.value, "moderation_status": product.moderation_status.value}
        audit = self._audit(
            event_type="PRODUCT_MODERATED_STATUS_CHANGED",
            entity_type="marketplace_product",
            entity_id=str(product.id),
            action="PRODUCT_MODERATED_STATUS_CHANGED",
            before=before,
            after=after,
            reason=reason,
        )
        product.audit_event_id = audit.id
        if status == MarketplaceProductStatus.PUBLISHED:
            record_decision_memory(
                self.db,
                case_id=None,
                decision_type="product_published",
                decision_ref_id=str(product.id),
                decision_at=now,
                decided_by_user_id=self.request_ctx.actor_id if self.request_ctx else None,
                context_snapshot={"product_id": str(product.id), "status": product.status.value},
                rationale=reason or "Product published",
                score_snapshot=None,
                mastery_snapshot=None,
                audit_event_id=str(audit.id),
            )
        self.db.flush()
        return product

    def approve_product(self, *, product: MarketplaceProduct) -> MarketplaceProduct:
        if product.moderation_status != MarketplaceProductModerationStatus.PENDING_REVIEW:
            raise ValueError("product_not_pending_review")
        before = {
            "status": product.status.value,
            "moderation_status": product.moderation_status.value,
        }
        now = datetime.now(timezone.utc)
        product.status = MarketplaceProductStatus.PUBLISHED
        product.moderation_status = MarketplaceProductModerationStatus.APPROVED
        product.moderation_reason = None
        product.moderated_by = self.request_ctx.actor_id if self.request_ctx else None
        product.moderated_at = now
        product.published_at = product.published_at or now
        product.updated_at = now
        after = {
            "status": product.status.value,
            "moderation_status": product.moderation_status.value,
        }
        audit = self._audit(
            event_type="PRODUCT_APPROVED",
            entity_type="marketplace_product",
            entity_id=str(product.id),
            action="PRODUCT_APPROVED",
            before=before,
            after=after,
        )
        product.audit_event_id = audit.id
        record_decision_memory(
            self.db,
            case_id=None,
            decision_type="product_approved",
            decision_ref_id=str(product.id),
            decision_at=now,
            decided_by_user_id=self.request_ctx.actor_id if self.request_ctx else None,
            context_snapshot={"product_id": str(product.id), "status": product.status.value},
            rationale="Product approved",
            score_snapshot=None,
            mastery_snapshot=None,
            audit_event_id=str(audit.id),
        )
        self.db.flush()
        return product

    def reject_product(self, *, product: MarketplaceProduct, reason: str) -> MarketplaceProduct:
        if product.moderation_status != MarketplaceProductModerationStatus.PENDING_REVIEW:
            raise ValueError("product_not_pending_review")
        if not reason:
            raise ValueError("moderation_reason_required")
        before = {
            "status": product.status.value,
            "moderation_status": product.moderation_status.value,
        }
        now = datetime.now(timezone.utc)
        product.moderation_status = MarketplaceProductModerationStatus.REJECTED
        product.moderation_reason = reason
        product.moderated_by = self.request_ctx.actor_id if self.request_ctx else None
        product.moderated_at = now
        product.published_at = None
        product.updated_at = now
        after = {
            "status": product.status.value,
            "moderation_status": product.moderation_status.value,
            "moderation_reason": product.moderation_reason,
        }
        audit = self._audit(
            event_type="PRODUCT_REJECTED",
            entity_type="marketplace_product",
            entity_id=str(product.id),
            action="PRODUCT_REJECTED",
            before=before,
            after=after,
            reason=reason,
        )
        product.audit_event_id = audit.id
        record_decision_memory(
            self.db,
            case_id=None,
            decision_type="product_rejected",
            decision_ref_id=str(product.id),
            decision_at=now,
            decided_by_user_id=self.request_ctx.actor_id if self.request_ctx else None,
            context_snapshot={"product_id": str(product.id), "status": product.status.value},
            rationale=reason,
            score_snapshot=None,
            mastery_snapshot=None,
            audit_event_id=str(audit.id),
        )
        self.db.flush()
        return product

    def list_published_products(
        self,
        *,
        product_type: MarketplaceProductType | None = None,
        category: str | None = None,
        query_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceProduct], int]:
        query = self.db.query(MarketplaceProduct).filter(
            MarketplaceProduct.status == MarketplaceProductStatus.PUBLISHED,
            MarketplaceProduct.moderation_status == MarketplaceProductModerationStatus.APPROVED,
        )
        if product_type:
            query = query.filter(MarketplaceProduct.type == product_type)
        if category:
            query = query.filter(MarketplaceProduct.category == category)
        if query_text:
            like = f"%{query_text}%"
            query = query.filter(
                or_(
                    MarketplaceProduct.title.ilike(like),
                    MarketplaceProduct.description.ilike(like),
                )
            )
        total = query.count()
        items = (
            query.order_by(MarketplaceProduct.published_at.desc().nullslast(), MarketplaceProduct.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def get_published_product(self, *, product_id: str) -> MarketplaceProduct | None:
        return (
            self.db.query(MarketplaceProduct)
            .filter(
                MarketplaceProduct.id == product_id,
                MarketplaceProduct.status == MarketplaceProductStatus.PUBLISHED,
                MarketplaceProduct.moderation_status == MarketplaceProductModerationStatus.APPROVED,
            )
            .one_or_none()
        )

    def get_product(self, *, product_id: str) -> MarketplaceProduct | None:
        return self.db.query(MarketplaceProduct).filter(MarketplaceProduct.id == product_id).one_or_none()

    def list_admin_products(
        self,
        *,
        status: MarketplaceProductStatus | None = None,
        moderation_status: MarketplaceProductModerationStatus | None = None,
        partner_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceProduct], int]:
        query = self.db.query(MarketplaceProduct)
        if status:
            query = query.filter(MarketplaceProduct.status == status)
        if moderation_status:
            query = query.filter(MarketplaceProduct.moderation_status == moderation_status)
        if partner_id:
            query = query.filter(MarketplaceProduct.partner_id == partner_id)
        total = query.count()
        items = (
            query.order_by(MarketplaceProduct.updated_at.desc().nullslast(), MarketplaceProduct.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def list_moderation_queue(
        self,
        *,
        status: MarketplaceProductModerationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceProduct], int]:
        query = self.db.query(MarketplaceProduct)
        if status:
            query = query.filter(MarketplaceProduct.moderation_status == status)
        total = query.count()
        items = (
            query.order_by(MarketplaceProduct.updated_at.desc().nullslast(), MarketplaceProduct.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total
