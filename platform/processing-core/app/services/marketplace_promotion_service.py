from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_catalog import MarketplaceProduct
from app.models.marketplace_promotions import (
    MarketplacePromotion,
    MarketplacePromotionStatus,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.partner_subscription_service import PartnerSubscriptionService


class MarketplacePromotionServiceError(ValueError):
    def __init__(self, code: str, *, detail: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


@dataclass(frozen=True)
class PromotionListResult:
    items: list[MarketplacePromotion]
    total: int


class MarketplacePromotionService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx
        self.audit_service = AuditService(db)
        self.subscription_service = PartnerSubscriptionService(db)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _audit(
        self,
        *,
        event_type: str,
        entity_id: str,
        action: str,
        before: dict | None = None,
        after: dict | None = None,
    ) -> None:
        self.audit_service.audit(
            event_type=event_type,
            entity_type="marketplace_promotion",
            entity_id=entity_id,
            action=action,
            before=before,
            after=after,
            request_ctx=self.request_ctx,
        )

    def _ensure_subscription_allows_promotions(self, *, partner_id: str) -> None:
        subscription = self.subscription_service.ensure_subscription(partner_id=partner_id)
        features = subscription.features or {}
        if not features.get("can_create_discounts", False):
            raise MarketplacePromotionServiceError("subscription_forbidden")

    def _ensure_free_plan_limits(self, *, partner_id: str) -> None:
        subscription = self.subscription_service.ensure_subscription(partner_id=partner_id)
        if subscription.plan_code != "FREE":
            return
        active_count = (
            self.db.query(MarketplacePromotion)
            .filter(MarketplacePromotion.partner_id == partner_id)
            .filter(MarketplacePromotion.status == MarketplacePromotionStatus.ACTIVE.value)
            .count()
        )
        if active_count >= 1:
            raise MarketplacePromotionServiceError("free_plan_active_limit_reached")

    def _validate_rules(self, rules: dict) -> None:
        discount_type = rules.get("discount_type")
        if discount_type not in {"PERCENT", "FIXED"}:
            raise MarketplacePromotionServiceError("invalid_discount_type")
        discount_value = Decimal(str(rules.get("discount_value", 0)))
        if discount_value <= 0:
            raise MarketplacePromotionServiceError("invalid_discount_value")
        stacking = rules.get("stacking")
        if stacking and stacking != "BEST_ONLY":
            raise MarketplacePromotionServiceError("invalid_stacking_rule")

    def _validate_scope(self, *, partner_id: str, scope: dict) -> None:
        scope_type = scope.get("type")
        if scope_type == "PRODUCT":
            product_ids = scope.get("product_ids") or []
            if not product_ids:
                raise MarketplacePromotionServiceError("invalid_scope")
            count = (
                self.db.query(MarketplaceProduct)
                .filter(MarketplaceProduct.partner_id == partner_id)
                .filter(MarketplaceProduct.id.in_(product_ids))
                .count()
            )
            if count != len(product_ids):
                raise MarketplacePromotionServiceError("invalid_scope")
            return
        if scope_type == "CATEGORY":
            category_codes = scope.get("category_codes") or []
            if not category_codes:
                raise MarketplacePromotionServiceError("invalid_scope")
            return
        if scope_type == "PARTNER":
            if scope.get("partner_id") and str(scope.get("partner_id")) != str(partner_id):
                raise MarketplacePromotionServiceError("invalid_scope")
            return
        raise MarketplacePromotionServiceError("invalid_scope")

    def list_promotions(
        self,
        *,
        partner_id: str,
        status: MarketplacePromotionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PromotionListResult:
        query = self.db.query(MarketplacePromotion).filter(MarketplacePromotion.partner_id == partner_id)
        if status:
            query = query.filter(MarketplacePromotion.status == status.value)
        total = query.count()
        items = (
            query.order_by(MarketplacePromotion.created_at.desc(), MarketplacePromotion.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return PromotionListResult(items=items, total=total)

    def get_promotion(self, *, promotion_id: str) -> MarketplacePromotion | None:
        return self.db.query(MarketplacePromotion).filter(MarketplacePromotion.id == promotion_id).one_or_none()

    def create_promotion(
        self,
        *,
        partner_id: str,
        payload: dict,
    ) -> MarketplacePromotion:
        self._ensure_subscription_allows_promotions(partner_id=partner_id)
        scope = payload.get("scope_json") or payload.get("scope") or {}
        rules = payload.get("rules_json") or payload.get("rules") or {}
        self._validate_scope(partner_id=partner_id, scope=scope)
        self._validate_rules(rules)
        promotion = MarketplacePromotion(
            id=new_uuid_str(),
            partner_id=partner_id,
            promo_type=payload["promo_type"],
            status=MarketplacePromotionStatus.DRAFT.value,
            title=payload["title"],
            description=payload.get("description"),
            scope_json=scope,
            eligibility_json=payload.get("eligibility_json") or payload.get("eligibility"),
            rules_json=rules,
            schedule_json=payload.get("schedule_json") or payload.get("schedule"),
            limits_json=payload.get("limits_json") or payload.get("limits"),
            created_by=self.request_ctx.actor_id if self.request_ctx else None,
            updated_by=self.request_ctx.actor_id if self.request_ctx else None,
        )
        self.db.add(promotion)
        self.db.flush()
        self._audit(
            event_type="PROMOTION_CREATED",
            entity_id=str(promotion.id),
            action="PROMOTION_CREATED",
            after={
                "status": promotion.status,
                "promo_type": promotion.promo_type,
                "title": promotion.title,
            },
        )
        return promotion

    def update_promotion(self, *, promotion: MarketplacePromotion, payload: dict) -> MarketplacePromotion:
        if promotion.status in {MarketplacePromotionStatus.ENDED.value, MarketplacePromotionStatus.ARCHIVED.value}:
            raise MarketplacePromotionServiceError("promotion_locked")
        before = {
            "title": promotion.title,
            "description": promotion.description,
            "scope_json": promotion.scope_json,
            "eligibility_json": promotion.eligibility_json,
            "rules_json": promotion.rules_json,
            "schedule_json": promotion.schedule_json,
            "limits_json": promotion.limits_json,
        }
        if "scope_json" in payload:
            self._validate_scope(partner_id=str(promotion.partner_id), scope=payload["scope_json"])
            promotion.scope_json = payload["scope_json"]
        if "rules_json" in payload:
            self._validate_rules(payload["rules_json"])
            promotion.rules_json = payload["rules_json"]
        if "eligibility_json" in payload:
            promotion.eligibility_json = payload["eligibility_json"]
        if "schedule_json" in payload:
            promotion.schedule_json = payload["schedule_json"]
        if "limits_json" in payload:
            promotion.limits_json = payload["limits_json"]
        if "title" in payload and payload["title"] is not None:
            promotion.title = payload["title"]
        if "description" in payload:
            promotion.description = payload["description"]
        promotion.updated_at = self._now()
        promotion.updated_by = self.request_ctx.actor_id if self.request_ctx else None
        after = {
            "title": promotion.title,
            "description": promotion.description,
            "scope_json": promotion.scope_json,
            "eligibility_json": promotion.eligibility_json,
            "rules_json": promotion.rules_json,
            "schedule_json": promotion.schedule_json,
            "limits_json": promotion.limits_json,
        }
        self._audit(
            event_type="PROMOTION_UPDATED",
            entity_id=str(promotion.id),
            action="PROMOTION_UPDATED",
            before=before,
            after=after,
        )
        return promotion

    def set_status(self, *, promotion: MarketplacePromotion, status: MarketplacePromotionStatus) -> MarketplacePromotion:
        if status == MarketplacePromotionStatus.ACTIVE:
            self._ensure_subscription_allows_promotions(partner_id=str(promotion.partner_id))
            self._ensure_free_plan_limits(partner_id=str(promotion.partner_id))
        before = {"status": promotion.status}
        promotion.status = status.value
        promotion.updated_at = self._now()
        promotion.updated_by = self.request_ctx.actor_id if self.request_ctx else None
        after = {"status": promotion.status}
        self._audit(
            event_type=f"PROMOTION_{status.value}",
            entity_id=str(promotion.id),
            action=f"PROMOTION_{status.value}",
            before=before,
            after=after,
        )
        return promotion
