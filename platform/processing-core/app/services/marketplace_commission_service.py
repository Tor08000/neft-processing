from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.marketplace_commissions import (
    MarketplaceCommissionRule,
    MarketplaceCommissionScope,
    MarketplaceCommissionStatus,
    MarketplaceCommissionType,
)
from app.models.marketplace_orders import MarketplaceOrder


@dataclass(frozen=True)
class CommissionSnapshot:
    rule_id: str | None
    commission_type: str
    rate: Decimal | None
    amount: Decimal
    min_commission: Decimal | None
    max_commission: Decimal | None


class MarketplaceCommissionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _decimal(value: object | None) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _select_rule(
        self,
        *,
        partner_id: str,
        product_category: str | None,
        now: datetime,
    ) -> MarketplaceCommissionRule | None:
        query = (
            self.db.query(MarketplaceCommissionRule)
            .filter(MarketplaceCommissionRule.scope == MarketplaceCommissionScope.MARKETPLACE)
            .filter(MarketplaceCommissionRule.status == MarketplaceCommissionStatus.ACTIVE)
            .filter(
                and_(
                    or_(MarketplaceCommissionRule.effective_from.is_(None), MarketplaceCommissionRule.effective_from <= now),
                    or_(MarketplaceCommissionRule.effective_to.is_(None), MarketplaceCommissionRule.effective_to >= now),
                )
            )
            .filter(
                and_(
                    or_(MarketplaceCommissionRule.partner_id.is_(None), MarketplaceCommissionRule.partner_id == partner_id),
                    or_(
                        MarketplaceCommissionRule.product_category.is_(None),
                        MarketplaceCommissionRule.product_category == product_category,
                    ),
                )
            )
            .order_by(MarketplaceCommissionRule.priority.desc(), MarketplaceCommissionRule.created_at.desc())
        )
        return query.first()

    def _apply_tiers(self, *, tiers: list[dict], basis: Decimal) -> tuple[Decimal, Decimal | None]:
        selected = None
        for tier in tiers:
            tier_from = self._decimal(tier.get("from", 0))
            tier_to = tier.get("to")
            tier_to_value = self._decimal(tier_to) if tier_to is not None else None
            if basis >= tier_from and (tier_to_value is None or basis <= tier_to_value):
                selected = tier
        if selected is None and tiers:
            selected = tiers[-1]
        if not selected:
            return Decimal("0"), None
        rate = selected.get("rate")
        amount = selected.get("amount")
        if rate is not None:
            rate_value = self._decimal(rate)
            return basis * rate_value, rate_value
        return self._decimal(amount), None

    def calculate_snapshot(
        self,
        *,
        order: MarketplaceOrder,
        product_category: str | None,
        subtotal: Decimal,
    ) -> CommissionSnapshot:
        now = self._now()
        rule = self._select_rule(partner_id=str(order.partner_id), product_category=product_category, now=now)
        commission_type = MarketplaceCommissionType.PERCENT.value
        amount = Decimal("0")
        rate: Decimal | None = None
        min_commission = None
        max_commission = None
        if rule:
            commission_type = rule.commission_type.value if hasattr(rule.commission_type, "value") else str(rule.commission_type)
            if commission_type == MarketplaceCommissionType.PERCENT.value:
                rate = self._decimal(rule.rate)
                amount = subtotal * rate
            elif commission_type == MarketplaceCommissionType.FIXED.value:
                amount = self._decimal(rule.amount)
            elif commission_type == MarketplaceCommissionType.TIERED.value:
                amount, rate = self._apply_tiers(tiers=rule.tiers or [], basis=subtotal)
            min_commission = self._decimal(rule.min_commission) if rule.min_commission is not None else None
            max_commission = self._decimal(rule.max_commission) if rule.max_commission is not None else None
        if min_commission is not None:
            amount = max(amount, min_commission)
        if max_commission is not None:
            amount = min(amount, max_commission)
        return CommissionSnapshot(
            rule_id=str(rule.id) if rule else None,
            commission_type=commission_type,
            rate=rate,
            amount=amount,
            min_commission=min_commission,
            max_commission=max_commission,
        )

    def apply_commission_snapshot(
        self,
        *,
        order: MarketplaceOrder,
        product_category: str | None,
        subtotal: Decimal,
    ) -> CommissionSnapshot:
        snapshot = self.calculate_snapshot(order=order, product_category=product_category, subtotal=subtotal)
        order.commission_snapshot = {
            "rule_id": snapshot.rule_id,
            "type": snapshot.commission_type,
            "rate": str(snapshot.rate) if snapshot.rate is not None else None,
            "amount": str(snapshot.amount),
            "min": str(snapshot.min_commission) if snapshot.min_commission is not None else None,
            "max": str(snapshot.max_commission) if snapshot.max_commission is not None else None,
        }
        order.commission = snapshot.amount
        return snapshot


__all__ = ["CommissionSnapshot", "MarketplaceCommissionService"]
