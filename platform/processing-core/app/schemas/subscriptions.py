from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.subscriptions_v1 import SubscriptionModuleCode, SubscriptionStatus


class SubscriptionPlanModuleBase(BaseModel):
    module_code: SubscriptionModuleCode
    enabled: bool = True
    tier: str | None = None
    limits: dict[str, Any] | None = None


class SubscriptionPlanModuleOut(SubscriptionPlanModuleBase):
    id: int | None = None


class SubscriptionPlanBase(BaseModel):
    code: str
    title: str
    description: str | None = None
    is_active: bool = True
    billing_period_months: int = 0
    price_cents: int = 0
    currency: str = "RUB"


class SubscriptionPlanCreate(SubscriptionPlanBase):
    modules: list[SubscriptionPlanModuleBase] | None = None


class SubscriptionPlanUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    description: str | None = None
    is_active: bool | None = None
    billing_period_months: int | None = None
    price_cents: int | None = None
    currency: str | None = None


class SubscriptionPlanOut(SubscriptionPlanBase):
    id: str
    modules: list[SubscriptionPlanModuleOut] = Field(default_factory=list)
    roles: list["RoleEntitlementOut"] = Field(default_factory=list)
    bonus_rules: list["BonusRuleOut"] = Field(default_factory=list)


class RoleEntitlementBase(BaseModel):
    role_code: str
    entitlements: dict[str, Any] | None = None


class RoleEntitlementOut(RoleEntitlementBase):
    id: int | None = None


class BonusRuleBase(BaseModel):
    plan_id: str | None = None
    rule_code: str
    title: str
    condition: dict[str, Any] | None = None
    reward: dict[str, Any] | None = None
    enabled: bool = True


class BonusRuleOut(BonusRuleBase):
    id: int


class BonusRuleUpdate(BaseModel):
    title: str | None = None
    condition: dict[str, Any] | None = None
    reward: dict[str, Any] | None = None
    enabled: bool | None = None


class ClientSubscriptionOut(BaseModel):
    id: str
    tenant_id: int
    client_id: str
    plan_id: str
    status: SubscriptionStatus
    start_at: datetime
    end_at: datetime | None = None
    auto_renew: bool
    grace_until: datetime | None = None
    plan: SubscriptionPlanOut | None = None


class SubscriptionBenefitsOut(BaseModel):
    plan: SubscriptionPlanOut
    modules: list[SubscriptionPlanModuleOut]
    unavailable_modules: list[SubscriptionPlanModuleOut]


class GamificationSummary(BaseModel):
    as_of: datetime
    plan_code: str
    bonuses: list[dict[str, Any]] = Field(default_factory=list)
    streaks: list[dict[str, Any]] = Field(default_factory=list)
    achievements: list[dict[str, Any]] = Field(default_factory=list)
    preview: dict[str, Any] | None = None


class AssignSubscriptionIn(BaseModel):
    plan_id: str
    duration_months: int | None = None
    auto_renew: bool = True


SubscriptionPlanOut.model_rebuild()
