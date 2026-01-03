from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_catalog import MarketplacePriceModel, MarketplaceProduct, MarketplaceProductStatus
from app.models.marketplace_orders import MarketplaceOrder
from app.models.marketplace_promotions import (
    MarketplaceCoupon,
    MarketplaceCouponBatch,
    MarketplaceCouponStatus,
    MarketplacePromotion,
    MarketplacePromotionApplication,
    MarketplacePromotionStatus,
)
from app.services.audit_service import AuditService, RequestContext


class MarketplacePricingServiceError(ValueError):
    def __init__(self, code: str, *, detail: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


@dataclass(frozen=True)
class PricingResult:
    price_snapshot: dict
    applied_promotion_id: str | None
    applied_coupon_id: str | None
    discount_amount: Decimal
    base_total: Decimal
    final_total: Decimal
    applied_promotions_json: dict | None
    decision_json: dict
    coupon_code: str | None


class MarketplacePricingService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx
        self.audit_service = AuditService(db)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _to_decimal(value: object) -> Decimal:
        return Decimal(str(value))

    def _calculate_price(self, *, price_model: str, price_config: dict, quantity: Decimal) -> Decimal:
        if price_model == MarketplacePriceModel.FIXED.value:
            return self._to_decimal(price_config.get("amount", 0))
        if price_model == MarketplacePriceModel.PER_UNIT.value:
            return self._to_decimal(price_config.get("amount_per_unit", 0)) * quantity
        if price_model == MarketplacePriceModel.TIERED.value:
            tiers = price_config.get("tiers") or []
            if not tiers:
                return Decimal("0")
            selected = None
            for tier in tiers:
                tier_from = self._to_decimal(tier.get("from", 0))
                tier_to = tier.get("to")
                tier_to_value = self._to_decimal(tier_to) if tier_to is not None else None
                if quantity >= tier_from and (tier_to_value is None or quantity <= tier_to_value):
                    selected = tier
            if selected is None:
                selected = tiers[-1]
            return self._to_decimal(selected.get("amount", 0)) * quantity
        return Decimal("0")

    @staticmethod
    def _parse_dt(value: str | datetime | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return None

    @staticmethod
    def _price_snapshot_hash(snapshot: dict) -> str:
        payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load_products(self, items: list[dict]) -> dict[str, MarketplaceProduct]:
        ids = [item["product_id"] for item in items]
        products = self.db.query(MarketplaceProduct).filter(MarketplaceProduct.id.in_(ids)).all()
        product_map = {str(product.id): product for product in products}
        if len(product_map) != len(ids):
            raise MarketplacePricingServiceError("product_not_found")
        for product in product_map.values():
            if product.status != MarketplaceProductStatus.PUBLISHED:
                raise MarketplacePricingServiceError("product_not_published")
        return product_map

    def _promotion_in_schedule(self, promotion: MarketplacePromotion) -> bool:
        schedule = promotion.schedule_json or {}
        valid_from = self._parse_dt(schedule.get("valid_from"))
        valid_to = self._parse_dt(schedule.get("valid_to"))
        now = self._now()
        if valid_from and now < valid_from:
            return False
        if valid_to and now > valid_to:
            return False
        return True

    def _promotion_eligible_for_client(self, promotion: MarketplacePromotion, client_id: str | None) -> bool:
        eligibility = promotion.eligibility_json or {}
        allowlist = eligibility.get("client_ids") or []
        if allowlist and client_id and client_id not in allowlist:
            return False
        return True

    def _promotion_limit_ok(self, promotion: MarketplacePromotion, client_id: str | None) -> bool:
        limits = promotion.limits_json or {}
        total_limit = limits.get("total_redemptions")
        if total_limit is not None:
            total_count = (
                self.db.query(MarketplacePromotionApplication)
                .filter(MarketplacePromotionApplication.promotion_id == promotion.id)
                .count()
            )
            if total_count >= total_limit:
                return False
        if client_id:
            per_client_total = limits.get("per_client_total")
            if per_client_total is not None:
                client_count = (
                    self.db.query(MarketplacePromotionApplication)
                    .filter(MarketplacePromotionApplication.promotion_id == promotion.id)
                    .filter(MarketplacePromotionApplication.client_id == client_id)
                    .count()
                )
                if client_count >= per_client_total:
                    return False
            per_client_per_day = limits.get("per_client_per_day")
            if per_client_per_day is not None:
                start_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                day_count = (
                    self.db.query(MarketplacePromotionApplication)
                    .filter(MarketplacePromotionApplication.promotion_id == promotion.id)
                    .filter(MarketplacePromotionApplication.client_id == client_id)
                    .filter(MarketplacePromotionApplication.created_at >= start_day)
                    .count()
                )
                if day_count >= per_client_per_day:
                    return False
        return True

    @staticmethod
    def _promotion_scope_total(promotion: MarketplacePromotion, items: list[dict], products: dict) -> Decimal:
        scope = promotion.scope_json or {}
        scope_type = scope.get("type")
        eligible_total = Decimal("0")
        for item in items:
            product = products[item["product_id"]]
            matches = False
            if scope_type == "PRODUCT":
                matches = item["product_id"] in (scope.get("product_ids") or [])
            elif scope_type == "CATEGORY":
                matches = product.category in (scope.get("category_codes") or [])
            elif scope_type == "PARTNER":
                matches = str(product.partner_id) == str(scope.get("partner_id") or product.partner_id)
            if matches:
                eligible_total += item["total"]
        return eligible_total

    def _evaluate_promotion(self, *, promotion: MarketplacePromotion, base_total: Decimal) -> tuple[Decimal, bool]:
        rules = promotion.rules_json or {}
        discount_type = rules.get("discount_type")
        discount_value = self._to_decimal(rules.get("discount_value", 0))
        discount_amount = Decimal("0")
        if discount_type == "PERCENT":
            discount_amount = base_total * discount_value / Decimal("100")
        elif discount_type == "FIXED":
            discount_amount = min(discount_value, base_total)
        max_discount = rules.get("max_discount")
        if max_discount is not None:
            max_discount_value = self._to_decimal(max_discount)
            discount_amount = min(discount_amount, max_discount_value)
        price_floor_hit = False
        price_floor = rules.get("price_floor")
        if price_floor is not None:
            floor_value = self._to_decimal(price_floor)
            if base_total - discount_amount < floor_value:
                discount_amount = max(Decimal("0"), base_total - floor_value)
                price_floor_hit = True
        return discount_amount, price_floor_hit

    def _load_coupon(self, code: str) -> MarketplaceCoupon | None:
        return (
            self.db.query(MarketplaceCoupon)
            .filter(MarketplaceCoupon.code == code)
            .one_or_none()
        )

    def quote(
        self,
        *,
        partner_id: str,
        client_id: str | None,
        items: list[dict],
        coupon_code: str | None = None,
    ) -> PricingResult:
        if not items:
            raise MarketplacePricingServiceError("items_required")
        products = self._load_products(items)
        partner_ids = {str(products[item["product_id"]].partner_id) for item in items}
        if len(partner_ids) != 1 or str(partner_id) not in partner_ids:
            raise MarketplacePricingServiceError("partner_mismatch")
        currency = None
        for item in items:
            product = products[item["product_id"]]
            price_model = product.price_model.value if hasattr(product.price_model, "value") else product.price_model
            item_total = self._calculate_price(
                price_model=price_model,
                price_config=product.price_config,
                quantity=item["quantity"],
            )
            item["total"] = item_total
            item_currency = product.price_config.get("currency")
            currency = currency or item_currency
            if currency != item_currency:
                raise MarketplacePricingServiceError("currency_mismatch")
        base_total = sum((item["total"] for item in items), Decimal("0"))

        candidate_promotions = (
            self.db.query(MarketplacePromotion)
            .filter(MarketplacePromotion.partner_id == partner_id)
            .filter(MarketplacePromotion.status == MarketplacePromotionStatus.ACTIVE.value)
            .all()
        )
        decision_promotions: list[dict] = []
        eligible_promotions: list[tuple[MarketplacePromotion, Decimal, bool]] = []
        for promotion in candidate_promotions:
            if not self._promotion_in_schedule(promotion):
                decision_promotions.append({"promotion_id": str(promotion.id), "eligible": False, "reason": "schedule"})
                continue
            if not self._promotion_eligible_for_client(promotion, client_id):
                decision_promotions.append({"promotion_id": str(promotion.id), "eligible": False, "reason": "eligibility"})
                continue
            if not self._promotion_limit_ok(promotion, client_id):
                decision_promotions.append({"promotion_id": str(promotion.id), "eligible": False, "reason": "limits"})
                continue
            scope_total = self._promotion_scope_total(promotion, items, products)
            if scope_total <= 0:
                decision_promotions.append({"promotion_id": str(promotion.id), "eligible": False, "reason": "scope"})
                continue
            discount_amount, price_floor_hit = self._evaluate_promotion(promotion=promotion, base_total=scope_total)
            eligible_promotions.append((promotion, discount_amount, price_floor_hit))
            decision_promotions.append({"promotion_id": str(promotion.id), "eligible": True})

        applied_promotion = None
        applied_discount = Decimal("0")
        price_floor_hit = False
        if eligible_promotions:
            applied_promotion, applied_discount, price_floor_hit = max(
                eligible_promotions, key=lambda item: item[1]
            )

        applied_coupon = None
        coupon_decision: dict | None = None
        if coupon_code:
            coupon = self._load_coupon(coupon_code)
            if not coupon:
                coupon_decision = {"code": coupon_code, "eligible": False, "reason": "not_found"}
            else:
                if coupon.status not in {MarketplaceCouponStatus.NEW.value, MarketplaceCouponStatus.ISSUED.value}:
                    coupon_decision = {"code": coupon_code, "eligible": False, "reason": "status"}
                elif coupon.expires_at and coupon.expires_at < self._now():
                    coupon_decision = {"code": coupon_code, "eligible": False, "reason": "expired"}
                elif coupon.client_id and client_id and str(coupon.client_id) != str(client_id):
                    coupon_decision = {"code": coupon_code, "eligible": False, "reason": "client_mismatch"}
                else:
                    promotion = self.db.query(MarketplacePromotion).filter(MarketplacePromotion.id == coupon.promotion_id).one()
                    if promotion.status != MarketplacePromotionStatus.ACTIVE.value:
                        coupon_decision = {"code": coupon_code, "eligible": False, "reason": "promotion_status"}
                    elif not self._promotion_in_schedule(promotion):
                        coupon_decision = {"code": coupon_code, "eligible": False, "reason": "schedule"}
                    elif not self._promotion_eligible_for_client(promotion, client_id):
                        coupon_decision = {"code": coupon_code, "eligible": False, "reason": "eligibility"}
                    elif not self._promotion_limit_ok(promotion, client_id):
                        coupon_decision = {"code": coupon_code, "eligible": False, "reason": "limits"}
                    else:
                        scope_total = self._promotion_scope_total(promotion, items, products)
                        discount_amount, price_floor_hit = self._evaluate_promotion(
                            promotion=promotion, base_total=scope_total
                        )
                        applied_promotion = promotion
                        applied_discount = discount_amount
                        applied_coupon = coupon
                        coupon_decision = {"code": coupon_code, "eligible": True, "reason": "override"}

        discounts = []
        if applied_promotion:
            discounts.append(
                {
                    "type": "PROMOTION",
                    "promotion_id": str(applied_promotion.id),
                    "title": applied_promotion.title,
                    "discount_amount": float(applied_discount),
                }
            )
        if coupon_code:
            discounts.append(
                {
                    "type": "COUPON",
                    "coupon_code": coupon_code,
                    "coupon_id": str(applied_coupon.id) if applied_coupon else None,
                    "discount_amount": float(applied_discount if applied_coupon else 0),
                }
            )
        final_total = base_total - applied_discount
        price_snapshot = {
            "base": {"items_total": float(base_total), "currency": currency},
            "discounts": discounts,
            "rules": {"stacking": "BEST_ONLY", "price_floor_hit": price_floor_hit},
            "final": {"items_total": float(final_total)},
            "meta": {"calculated_at": self._now().isoformat(), "engine": "promo_pricing_v1"},
        }
        applied_promotions_json = None
        if applied_promotion:
            applied_promotions_json = {
                "promotion_id": str(applied_promotion.id),
                "coupon_id": str(applied_coupon.id) if applied_coupon else None,
                "discount_amount": float(applied_discount),
            }
        decision_json = {"promotions": decision_promotions, "coupon": coupon_decision}
        return PricingResult(
            price_snapshot=price_snapshot,
            applied_promotion_id=str(applied_promotion.id) if applied_promotion else None,
            applied_coupon_id=str(applied_coupon.id) if applied_coupon else None,
            discount_amount=applied_discount,
            base_total=base_total,
            final_total=final_total,
            applied_promotions_json=applied_promotions_json,
            decision_json=decision_json,
            coupon_code=coupon_code,
        )

    def apply_pricing_to_order(
        self,
        *,
        order: MarketplaceOrder,
        pricing: PricingResult,
        client_id: str,
        partner_id: str,
    ) -> None:
        if not pricing.applied_promotion_id:
            return
        coupon_id = pricing.applied_coupon_id
        promotion_application = MarketplacePromotionApplication(
            id=new_uuid_str(),
            order_id=order.id,
            partner_id=partner_id,
            client_id=client_id,
            promotion_id=pricing.applied_promotion_id,
            coupon_id=coupon_id,
            applied_discount=pricing.discount_amount,
            currency=pricing.price_snapshot["base"]["currency"],
            price_snapshot_json=pricing.price_snapshot,
            decision_json=pricing.decision_json,
        )
        self.db.add(promotion_application)
        if coupon_id:
            coupon = self.db.query(MarketplaceCoupon).filter(MarketplaceCoupon.id == coupon_id).one()
            if coupon.status in {MarketplaceCouponStatus.NEW.value, MarketplaceCouponStatus.ISSUED.value}:
                coupon.status = MarketplaceCouponStatus.REDEEMED.value
                coupon.redeemed_at = self._now()
                coupon.redeemed_order_id = order.id
                batch = self.db.query(MarketplaceCouponBatch).filter(MarketplaceCouponBatch.id == coupon.batch_id).one()
                batch.redeemed_count = (batch.redeemed_count or 0) + 1
                self.audit_service.audit(
                    event_type="COUPON_REDEEMED",
                    entity_type="marketplace_coupon",
                    entity_id=str(coupon.id),
                    action="COUPON_REDEEMED",
                    after={"order_id": str(order.id), "code": coupon.code},
                    request_ctx=self.request_ctx,
                )
        self.audit_service.audit(
            event_type="PROMOTION_APPLIED_TO_ORDER",
            entity_type="marketplace_order",
            entity_id=str(order.id),
            action="PROMOTION_APPLIED_TO_ORDER",
            after={
                "promotion_id": pricing.applied_promotion_id,
                "coupon_id": coupon_id,
                "price_snapshot_hash": self._price_snapshot_hash(pricing.price_snapshot),
            },
            request_ctx=self.request_ctx,
        )
