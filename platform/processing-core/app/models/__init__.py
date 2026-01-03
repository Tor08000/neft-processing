"""Lightweight model exports.

Avoid eager imports to prevent circular dependencies. Use lazy attribute access for
marketplace promotion/coupon compatibility.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_SIMPLE_EXPORTS = {
    "Card": "app.models.card",
    "Client": "app.models.client",
    "ImmutableRecordError": "app.models.immutability",
    "Merchant": "app.models.merchant",
    "Partner": "app.models.partner",
    "Terminal": "app.models.terminal",
}

_MARKETPLACE_PROMOTIONS_EXPORTS = {
    "Coupon",
    "CouponBatch",
    "CouponStatus",
    "MarketplaceCoupon",
    "MarketplaceCouponBatch",
    "MarketplaceCouponBatchType",
    "MarketplaceCouponStatus",
    "MarketplacePromotion",
    "MarketplacePromotionApplication",
    "MarketplacePromotionStatus",
    "MarketplacePromotionType",
    "MissionProgressStatus",
    "PartnerBadge",
    "PartnerBadgeAward",
    "PartnerMission",
    "PartnerMissionProgress",
    "PartnerTier",
    "PartnerTierState",
    "PromoBudget",
    "PromoBudgetModel",
    "PromoBudgetStatus",
    "Promotion",
    "PromotionApplication",
    "PromotionApplicationImmutableError",
    "PromotionStatus",
    "PromotionType",
}

__all__ = [
    *sorted(_SIMPLE_EXPORTS.keys()),
    "groups",
    *sorted(_MARKETPLACE_PROMOTIONS_EXPORTS),
]


def __getattr__(name: str) -> Any:
    if name in _SIMPLE_EXPORTS:
        module = import_module(_SIMPLE_EXPORTS[name])
        return getattr(module, name)

    if name == "groups":
        return import_module("app.models.groups")

    if name in _MARKETPLACE_PROMOTIONS_EXPORTS:
        module = import_module("app.models.marketplace_promotions")
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__))
