from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_catalog import MarketplaceProduct
from app.models.marketplace_orders import MarketplaceOrder
from app.models.marketplace_promotions import (
    Coupon,
    CouponBatch,
    CouponStatus,
    Promotion,
    PromotionApplication,
    PromotionStatus,
    PromotionType,
)
from app.services.audit_service import AuditService, RequestContext


@dataclass(frozen=True)
class PromotionPriceResult:
    base_price: Decimal
    discount_total: Decimal
    final_price: Decimal
    applied_promotions: list[Promotion]
    applied_discounts: dict[str, Decimal]
    applied_rules: dict
    price_snapshot: dict


class MarketplacePromotionServiceError(ValueError):
    def __init__(self, code: str, *, detail: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


class MarketplacePromotionService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx
        self.audit_service = AuditService(db)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _tenant_id(self) -> int:
        if self.request_ctx and self.request_ctx.tenant_id is not None:
            return int(self.request_ctx.tenant_id)
        return 0

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

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)

    def _is_schedule_active(self, schedule: dict | None, now: datetime) -> bool:
        if not schedule:
            return True
        valid_from = self._parse_datetime(schedule.get("valid_from"))
        valid_to = self._parse_datetime(schedule.get("valid_to"))
        if valid_from and now < valid_from:
            return False
        if valid_to and now > valid_to:
            return False
        return True

    def _is_scope_match(self, scope: dict | None, product: MarketplaceProduct) -> bool:
        if not scope:
            return True
        scope_type = scope.get("type")
        if scope_type == "PRODUCT":
            product_ids = scope.get("product_ids") or []
            return str(product.id) in {str(pid) for pid in product_ids}
        if scope_type == "CATEGORY":
            categories = scope.get("category_codes") or []
            return product.category in categories
        return True

    def _is_eligible(self, eligibility: dict | None, client_id: str) -> bool:
        if not eligibility:
            return True
        client_ids = eligibility.get("client_ids") or []
        if client_ids and client_id not in {str(cid) for cid in client_ids}:
            return False
        return True

    def _calculate_base_price(self, product: MarketplaceProduct, quantity: Decimal) -> Decimal:
        price_model = product.price_model.value if hasattr(product.price_model, "value") else product.price_model
        config = product.price_config or {}
        if price_model == "FIXED":
            return Decimal(str(config.get("amount", 0)))
        if price_model == "PER_UNIT":
            return Decimal(str(config.get("amount_per_unit", 0))) * quantity
        if price_model == "TIERED":
            tiers = config.get("tiers") or []
            best_amount: Decimal | None = None
            for tier in tiers:
                tier_from = Decimal(str(tier.get("from", 0)))
                tier_to = tier.get("to")
                if quantity < tier_from:
                    continue
                if tier_to is not None and quantity > Decimal(str(tier_to)):
                    continue
                best_amount = Decimal(str(tier.get("amount", 0)))
            if best_amount is None and tiers:
                best_amount = Decimal(str(tiers[-1].get("amount", 0)))
            return best_amount or Decimal("0")
        return Decimal("0")

    def _calculate_discount(self, promotion: Promotion, base_price: Decimal) -> Decimal:
        rules = promotion.rules or {}
        discount_type = rules.get("discount_type", "PERCENT")
        discount_value = Decimal(str(rules.get("discount_value", 0)))
        if discount_type == "PERCENT":
            discount = base_price * discount_value / Decimal("100")
        else:
            discount = discount_value
        max_discount = rules.get("max_discount")
        if max_discount is not None:
            discount = min(discount, Decimal(str(max_discount)))
        price_floor = rules.get("price_floor")
        if price_floor is not None:
            floor_value = Decimal(str(price_floor))
            if base_price <= floor_value:
                return Decimal("0")
            discount = min(discount, base_price - floor_value)
        return max(discount, Decimal("0"))

    def _stacking_mode(self, promotions: list[Promotion]) -> str:
        if not promotions:
            return "BEST_ONLY"
        modes = {str((promotion.rules or {}).get("stacking", "BEST_ONLY")) for promotion in promotions}
        if "NO_STACK" in modes or "BEST_ONLY" in modes:
            return "BEST_ONLY"
        return "ALLOW_STACK_WITH_CAP"

    def _stack_cap(self, promotions: list[Promotion], base_price: Decimal) -> Decimal | None:
        caps = []
        for promotion in promotions:
            cap_percent = (promotion.rules or {}).get("stack_cap_percent")
            if cap_percent is not None:
                caps.append(base_price * Decimal(str(cap_percent)) / Decimal("100"))
            cap_amount = (promotion.rules or {}).get("stack_cap_amount")
            if cap_amount is not None:
                caps.append(Decimal(str(cap_amount)))
        if not caps:
            return None
        return max(caps)

    def _price_snapshot(
        self,
        *,
        product: MarketplaceProduct,
        quantity: Decimal,
        base_price: Decimal,
        discount_total: Decimal,
        final_price: Decimal,
        applied_promotions: list[Promotion],
        applied_discounts: dict[str, Decimal] | None = None,
    ) -> dict:
        return {
            "price_model": product.price_model.value if hasattr(product.price_model, "value") else product.price_model,
            "price_config": product.price_config,
            "quantity": str(quantity),
            "base_price": str(base_price),
            "discount_total": str(discount_total),
            "final_price": str(final_price),
            "applied_promotions": [str(promo.id) for promo in applied_promotions],
            "applied_discounts": {key: str(value) for key, value in (applied_discounts or {}).items()},
        }

    def _resolve_coupon(self, coupon_code: str, client_id: str) -> Coupon:
        coupon = self.db.query(Coupon).filter(Coupon.code == coupon_code).one_or_none()
        if not coupon:
            raise MarketplacePromotionServiceError("coupon_not_found")
        status = coupon.status.value if hasattr(coupon.status, "value") else coupon.status
        if status in {CouponStatus.REDEEMED.value, CouponStatus.CANCELED.value, CouponStatus.EXPIRED.value}:
            raise MarketplacePromotionServiceError("coupon_not_active")
        now = self._now()
        if coupon.expires_at and coupon.expires_at <= now:
            coupon.status = CouponStatus.EXPIRED
            coupon.redeemed_at = now
            raise MarketplacePromotionServiceError("coupon_expired")
        if coupon.client_id and str(coupon.client_id) != client_id:
            raise MarketplacePromotionServiceError("coupon_forbidden")
        return coupon

    def get_promotion(self, *, promotion_id: str) -> Promotion | None:
        return self.db.query(Promotion).filter(Promotion.id == promotion_id).one_or_none()

    def list_promotions(
        self,
        *,
        partner_id: str,
        status: PromotionStatus | None = None,
        promo_type: PromotionType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Promotion], int]:
        query = self.db.query(Promotion).filter(Promotion.partner_id == partner_id)
        if status:
            query = query.filter(Promotion.status == status)
        if promo_type:
            query = query.filter(Promotion.promo_type == promo_type)
        total = query.count()
        items = (
            query.order_by(Promotion.created_at.desc(), Promotion.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def create_promotion(self, *, partner_id: str, payload: dict) -> Promotion:
        promotion_id = new_uuid_str()
        now = self._now()
        audit = self._audit(
            event_type="PROMOTION_CREATED",
            entity_type="promotion",
            entity_id=promotion_id,
            action="PROMOTION_CREATED",
            after=payload,
        )
        promotion = Promotion(
            id=promotion_id,
            tenant_id=self._tenant_id(),
            partner_id=partner_id,
            promo_type=payload["promo_type"],
            status=PromotionStatus.DRAFT.value,
            title=payload["title"],
            description=payload.get("description"),
            scope=payload.get("scope") or {},
            eligibility=payload.get("eligibility") or {},
            rules=payload.get("rules") or {},
            budget=payload.get("budget"),
            limits=payload.get("limits"),
            schedule=payload.get("schedule") or {},
            created_at=now,
            updated_at=now,
            audit_event_id=audit.id,
        )
        self.db.add(promotion)
        self.db.flush()
        return promotion

    def update_promotion(self, *, partner_id: str, promotion_id: str, payload: dict) -> Promotion:
        promotion = self.get_promotion(promotion_id=promotion_id)
        if not promotion:
            raise MarketplacePromotionServiceError("promotion_not_found")
        if str(promotion.partner_id) != partner_id:
            raise MarketplacePromotionServiceError("forbidden")
        before = {
            "title": promotion.title,
            "description": promotion.description,
            "scope": promotion.scope,
            "eligibility": promotion.eligibility,
            "rules": promotion.rules,
            "budget": promotion.budget,
            "limits": promotion.limits,
            "schedule": promotion.schedule,
            "status": promotion.status.value if hasattr(promotion.status, "value") else promotion.status,
        }
        for key, value in payload.items():
            if value is not None:
                setattr(promotion, key, value)
        promotion.updated_at = self._now()
        after = {
            "title": promotion.title,
            "description": promotion.description,
            "scope": promotion.scope,
            "eligibility": promotion.eligibility,
            "rules": promotion.rules,
            "budget": promotion.budget,
            "limits": promotion.limits,
            "schedule": promotion.schedule,
            "status": promotion.status.value if hasattr(promotion.status, "value") else promotion.status,
        }
        audit = self._audit(
            event_type="PROMOTION_UPDATED",
            entity_type="promotion",
            entity_id=str(promotion.id),
            action="PROMOTION_UPDATED",
            before=before,
            after=after,
        )
        promotion.audit_event_id = audit.id
        self.db.flush()
        return promotion

    def set_status(
        self,
        *,
        partner_id: str,
        promotion_id: str,
        status: PromotionStatus,
    ) -> Promotion:
        promotion = self.get_promotion(promotion_id=promotion_id)
        if not promotion:
            raise MarketplacePromotionServiceError("promotion_not_found")
        if str(promotion.partner_id) != partner_id:
            raise MarketplacePromotionServiceError("forbidden")
        before = {
            "status": promotion.status.value if hasattr(promotion.status, "value") else promotion.status,
        }
        promotion.status = status.value
        promotion.updated_at = self._now()
        after = {"status": status.value}
        audit = self._audit(
            event_type="PROMOTION_STATUS_CHANGED",
            entity_type="promotion",
            entity_id=str(promotion.id),
            action="PROMOTION_STATUS_CHANGED",
            before=before,
            after=after,
        )
        promotion.audit_event_id = audit.id
        self.db.flush()
        return promotion

    def list_active_promotions_for_product(
        self, *, partner_id: str, client_id: str, product: MarketplaceProduct
    ) -> list[Promotion]:
        now = self._now()
        promotions = (
            self.db.query(Promotion)
            .filter(Promotion.partner_id == partner_id)
            .filter(Promotion.status == PromotionStatus.ACTIVE)
            .all()
        )
        filtered: list[Promotion] = []
        for promotion in promotions:
            if promotion.promo_type == PromotionType.SPONSORED_PLACEMENT:
                continue
            if not self._is_schedule_active(promotion.schedule, now):
                continue
            if not self._is_scope_match(promotion.scope, product):
                continue
            if not self._is_eligible(promotion.eligibility, client_id):
                continue
            filtered.append(promotion)
        return filtered

    def list_active_deals(self, *, limit: int = 50, offset: int = 0) -> tuple[list[Promotion], int]:
        now = self._now()
        query = self.db.query(Promotion).filter(Promotion.status == PromotionStatus.ACTIVE)
        total = query.count()
        items = (
            query.order_by(Promotion.created_at.desc(), Promotion.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        filtered = [item for item in items if self._is_schedule_active(item.schedule, now)]
        return filtered, total

    def _evaluate_promotions(
        self,
        *,
        promotions: list[Promotion],
        product: MarketplaceProduct,
        quantity: Decimal,
    ) -> PromotionPriceResult:
        base_price = self._calculate_base_price(product, quantity)
        discounts = []
        for promotion in promotions:
            discount = self._calculate_discount(promotion, base_price)
            if discount > 0:
                discounts.append((promotion, discount))
        if not discounts:
            return PromotionPriceResult(
                base_price=base_price,
                discount_total=Decimal("0"),
                final_price=base_price,
                applied_promotions=[],
                applied_discounts={},
                applied_rules={},
                price_snapshot=self._price_snapshot(
                    product=product,
                    quantity=quantity,
                    base_price=base_price,
                    discount_total=Decimal("0"),
                    final_price=base_price,
                    applied_promotions=[],
                    applied_discounts={},
                ),
            )
        promotions_sorted = sorted(discounts, key=lambda item: item[1], reverse=True)
        stacking_mode = self._stacking_mode([item[0] for item in promotions_sorted])
        applied_discounts: dict[str, Decimal] = {}
        if stacking_mode == "BEST_ONLY":
            applied_promotions = [promotions_sorted[0][0]]
            discount_total = promotions_sorted[0][1]
            applied_discounts[str(promotions_sorted[0][0].id)] = promotions_sorted[0][1]
        else:
            applied_promotions = [item[0] for item in promotions_sorted]
            discount_total = sum((item[1] for item in promotions_sorted), Decimal("0"))
            for promotion, discount in promotions_sorted:
                applied_discounts[str(promotion.id)] = discount
            cap = self._stack_cap(applied_promotions, base_price)
            if cap is not None:
                if discount_total > 0:
                    scale = min(Decimal("1"), cap / discount_total)
                    discount_total = discount_total * scale
                    applied_discounts = {key: value * scale for key, value in applied_discounts.items()}
        price_floor = None
        for promotion in applied_promotions:
            floor_value = (promotion.rules or {}).get("price_floor")
            if floor_value is not None:
                floor_value = Decimal(str(floor_value))
                price_floor = max(price_floor or floor_value, floor_value)
        final_price = base_price - discount_total
        if price_floor is not None and final_price < price_floor:
            final_price = price_floor
            discount_total = base_price - final_price
            if discount_total > 0:
                total_before_floor = sum(applied_discounts.values(), Decimal("0"))
                if total_before_floor > 0:
                    scale = discount_total / total_before_floor
                    applied_discounts = {key: value * scale for key, value in applied_discounts.items()}
        final_price = max(final_price, Decimal("0"))
        return PromotionPriceResult(
            base_price=base_price,
            discount_total=discount_total,
            final_price=final_price,
            applied_promotions=applied_promotions,
            applied_discounts=applied_discounts,
            applied_rules={"stacking": stacking_mode},
            price_snapshot=self._price_snapshot(
                product=product,
                quantity=quantity,
                base_price=base_price,
                discount_total=discount_total,
                final_price=final_price,
                applied_promotions=applied_promotions,
                applied_discounts=applied_discounts,
            ),
        )

    def evaluate_promotions_for_quote(
        self,
        *,
        product: MarketplaceProduct,
        quantity: Decimal,
        client_id: str,
        promotion_id: str | None = None,
        coupon_code: str | None = None,
    ) -> PromotionPriceResult:
        promotions = self.list_active_promotions_for_product(
            partner_id=str(product.partner_id),
            client_id=client_id,
            product=product,
        )
        if promotion_id:
            promotions = [item for item in promotions if str(item.id) == promotion_id]
        if coupon_code:
            coupon = self._resolve_coupon(coupon_code, client_id)
            batch = self.db.query(CouponBatch).filter(CouponBatch.id == coupon.batch_id).one_or_none()
            if not batch:
                raise MarketplacePromotionServiceError("coupon_batch_not_found")
            promo = self.get_promotion(promotion_id=str(batch.promotion_id))
            if not promo:
                raise MarketplacePromotionServiceError("promotion_not_found")
            promo_status = promo.status.value if hasattr(promo.status, "value") else promo.status
            if promo_status != PromotionStatus.ACTIVE.value:
                raise MarketplacePromotionServiceError("promotion_not_active")
            if not self._is_schedule_active(promo.schedule, self._now()):
                raise MarketplacePromotionServiceError("promotion_not_active")
            if not self._is_scope_match(promo.scope, product):
                raise MarketplacePromotionServiceError("promotion_not_applicable")
            if not self._is_eligible(promo.eligibility, client_id):
                raise MarketplacePromotionServiceError("promotion_not_eligible")
            promotions = [promo]
        return self._evaluate_promotions(promotions=promotions, product=product, quantity=quantity)

    def apply_promotions_to_order(
        self,
        *,
        order: MarketplaceOrder,
        product: MarketplaceProduct,
        quantity: Decimal,
        client_id: str,
        promotion_id: str | None = None,
        coupon_code: str | None = None,
    ) -> PromotionPriceResult:
        result = self.evaluate_promotions_for_quote(
            product=product,
            quantity=quantity,
            client_id=client_id,
            promotion_id=promotion_id,
            coupon_code=coupon_code,
        )
        for promotion in result.applied_promotions:
            application_id = new_uuid_str()
            audit = self._audit(
                event_type="PROMOTION_APPLIED",
                entity_type="promotion_application",
                entity_id=application_id,
                action="PROMOTION_APPLIED",
                after={
                    "promotion_id": str(promotion.id),
                    "order_id": str(order.id),
                    "discount": str(result.applied_discounts.get(str(promotion.id), Decimal("0"))),
                },
            )
            application = PromotionApplication(
                id=application_id,
                tenant_id=self._tenant_id(),
                promotion_id=promotion.id,
                order_id=order.id,
                partner_id=order.partner_id,
                client_id=order.client_id,
                applied_discount=result.applied_discounts.get(str(promotion.id), Decimal("0")),
                applied_reason={
                    "promotion_id": str(promotion.id),
                    "stacking": result.applied_rules.get("stacking"),
                    "coupon_code": coupon_code,
                },
                final_price_snapshot=result.price_snapshot,
                created_at=self._now(),
                audit_event_id=audit.id,
            )
            self.db.add(application)
        if coupon_code:
            coupon = self._resolve_coupon(coupon_code, client_id)
            coupon.status = CouponStatus.REDEEMED
            coupon.redeemed_at = self._now()
            coupon.redeemed_order_id = order.id
            batch = self.db.query(CouponBatch).filter(CouponBatch.id == coupon.batch_id).one_or_none()
            if batch:
                batch.redeemed_count = (batch.redeemed_count or 0) + 1
        return result

    def promotion_stats(self, *, partner_id: str, promotion_id: str) -> dict:
        promo = self.get_promotion(promotion_id=promotion_id)
        if not promo:
            raise MarketplacePromotionServiceError("promotion_not_found")
        if str(promo.partner_id) != partner_id:
            raise MarketplacePromotionServiceError("forbidden")
        query = self.db.query(PromotionApplication).filter(PromotionApplication.promotion_id == promotion_id)
        totals = query.with_entities(
            func.count(PromotionApplication.id),
            func.coalesce(func.sum(PromotionApplication.applied_discount), 0),
            func.max(PromotionApplication.created_at),
        ).one()
        return {
            "promotion_id": promotion_id,
            "orders_count": int(totals[0] or 0),
            "total_discount": Decimal(str(totals[1] or 0)),
            "last_applied_at": totals[2],
        }


__all__ = [
    "MarketplacePromotionService",
    "MarketplacePromotionServiceError",
    "PromotionPriceResult",
]
