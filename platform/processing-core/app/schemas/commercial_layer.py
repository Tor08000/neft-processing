from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.commercial_layer import PlanBillingPeriod, PlanFeatureCode, UsageMetric
from app.models.subscriptions_v1 import SubscriptionStatus


class PlanFeatureBase(BaseModel):
    feature: PlanFeatureCode
    enabled: bool
    limits: dict[str, Any] | None = None


class PlanFeatureOut(PlanFeatureBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class PlanBase(BaseModel):
    code: str
    name: str
    description: str | None = None
    base_price_monthly: Decimal
    currency: str
    billing_period: PlanBillingPeriod
    active: bool = True


class PlanCreate(PlanBase):
    features: list[PlanFeatureBase] | None = None


class PlanOut(PlanBase):
    id: UUID
    features: list[PlanFeatureOut]

    model_config = ConfigDict(from_attributes=True)


class UsageCounterOut(BaseModel):
    metric: UsageMetric
    period_start: datetime
    period_end: datetime
    value: Decimal

    model_config = ConfigDict(from_attributes=True)


class UsageLimitSummary(BaseModel):
    metric: UsageMetric
    used: Decimal
    limit: Decimal | None = None
    overage: Decimal | None = None


class BillingPlanSummary(BaseModel):
    plan: PlanOut | None = None
    subscription_status: SubscriptionStatus | None = None
    started_at: datetime | None = None
    ends_at: datetime | None = None
    next_invoice_date: datetime | None = None
    usage: list[UsageLimitSummary]


class BillingUsageSummary(BaseModel):
    period_start: datetime
    period_end: datetime
    usage: list[UsageCounterOut]
    overages: list[UsageLimitSummary]


class UpgradeRequest(BaseModel):
    plan_id: UUID
    auto_upgrade: bool = False


class UpgradeResponse(BaseModel):
    subscription_id: str
    status: SubscriptionStatus


class ClientBrandingBase(BaseModel):
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    support_email: str | None = None
    portal_domain: str | None = None


class ClientBrandingOut(ClientBrandingBase):
    client_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientBrandingUpdate(ClientBrandingBase):
    pass


class OnboardingStepUpdate(BaseModel):
    step: str
    completed: bool = True
    load_demo_data: bool = False


class OnboardingStateOut(BaseModel):
    client_id: UUID
    current_step: str | None = None
    completed_steps: dict[str, bool] | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
