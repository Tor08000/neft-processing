from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_promotions import (
    MarketplaceCoupon,
    MarketplaceCouponBatch,
    MarketplaceCouponBatchType,
    MarketplaceCouponStatus,
    MarketplacePromotion,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.partner_subscription_service import PartnerSubscriptionService


class MarketplaceCouponServiceError(ValueError):
    def __init__(self, code: str, *, detail: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


@dataclass(frozen=True)
class CouponBatchListResult:
    items: list[MarketplaceCouponBatch]
    total: int


class MarketplaceCouponService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx
        self.audit_service = AuditService(db)
        self.subscription_service = PartnerSubscriptionService(db)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _audit(self, *, event_type: str, entity_id: str, action: str, after: dict | None = None) -> None:
        self.audit_service.audit(
            event_type=event_type,
            entity_type="marketplace_coupon",
            entity_id=entity_id,
            action=action,
            after=after,
            request_ctx=self.request_ctx,
        )

    def _ensure_subscription_allows_coupons(self, *, partner_id: str) -> None:
        subscription = self.subscription_service.ensure_subscription(partner_id=partner_id)
        features = subscription.features or {}
        if not features.get("can_create_discounts", False):
            raise MarketplaceCouponServiceError("subscription_forbidden")
        if subscription.plan_code == "FREE":
            raise MarketplaceCouponServiceError("subscription_forbidden")

    @staticmethod
    def _random_code(length: int = 8) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _generate_code(self, prefix: str | None) -> str:
        prefix_value = (prefix or "").upper()
        code = f"{prefix_value}{self._random_code(8)}"
        return code

    def list_batches(
        self,
        *,
        partner_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> CouponBatchListResult:
        query = self.db.query(MarketplaceCouponBatch).filter(MarketplaceCouponBatch.partner_id == partner_id)
        total = query.count()
        items = (
            query.order_by(MarketplaceCouponBatch.created_at.desc(), MarketplaceCouponBatch.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return CouponBatchListResult(items=items, total=total)

    def get_batch(self, *, batch_id: str) -> MarketplaceCouponBatch | None:
        return self.db.query(MarketplaceCouponBatch).filter(MarketplaceCouponBatch.id == batch_id).one_or_none()

    def create_batch(
        self,
        *,
        partner_id: str,
        payload: dict,
    ) -> MarketplaceCouponBatch:
        self._ensure_subscription_allows_coupons(partner_id=partner_id)
        promotion = (
            self.db.query(MarketplacePromotion)
            .filter(MarketplacePromotion.id == payload["promotion_id"])
            .one_or_none()
        )
        if not promotion or str(promotion.partner_id) != str(partner_id):
            raise MarketplaceCouponServiceError("promotion_not_found")
        batch = MarketplaceCouponBatch(
            id=new_uuid_str(),
            partner_id=partner_id,
            promotion_id=str(promotion.id),
            batch_type=payload["batch_type"],
            code_prefix=payload.get("code_prefix"),
            total_count=payload["total_count"],
            meta_json=payload.get("meta_json"),
        )
        self.db.add(batch)
        self.db.flush()
        expires_at = payload.get("expires_at")
        for _ in range(payload["total_count"]):
            code = self._generate_code(payload.get("code_prefix"))
            coupon = MarketplaceCoupon(
                id=new_uuid_str(),
                batch_id=batch.id,
                promotion_id=str(promotion.id),
                code=code,
                status=MarketplaceCouponStatus.NEW.value,
                expires_at=expires_at,
                created_at=self._now(),
            )
            self.db.add(coupon)
        self._audit(
            event_type="COUPON_BATCH_CREATED",
            entity_id=str(batch.id),
            action="COUPON_BATCH_CREATED",
            after={
                "batch_type": batch.batch_type,
                "total_count": batch.total_count,
                "promotion_id": str(batch.promotion_id),
            },
        )
        return batch

    def issue_coupon(self, *, batch: MarketplaceCouponBatch, client_id: str) -> MarketplaceCoupon:
        if batch.batch_type != MarketplaceCouponBatchType.TARGETED.value:
            raise MarketplaceCouponServiceError("invalid_batch_type")
        coupon = (
            self.db.query(MarketplaceCoupon)
            .filter(MarketplaceCoupon.batch_id == batch.id)
            .filter(MarketplaceCoupon.status == MarketplaceCouponStatus.NEW.value)
            .order_by(MarketplaceCoupon.created_at.asc(), MarketplaceCoupon.id.asc())
            .first()
        )
        if not coupon:
            raise MarketplaceCouponServiceError("no_available_coupons")
        coupon.status = MarketplaceCouponStatus.ISSUED.value
        coupon.client_id = client_id
        coupon.issued_at = self._now()
        batch.issued_count = (batch.issued_count or 0) + 1
        self._audit(
            event_type="COUPON_ISSUED",
            entity_id=str(coupon.id),
            action="COUPON_ISSUED",
            after={"client_id": client_id, "batch_id": str(batch.id)},
        )
        return coupon
