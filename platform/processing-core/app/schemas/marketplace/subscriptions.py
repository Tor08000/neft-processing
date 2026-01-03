from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PartnerPlanOut(BaseModel):
    plan_code: str
    title: str
    description: str | None = None
    base_commission: Decimal
    monthly_fee: Decimal
    features: dict | None = None
    limits: dict | None = None


class PartnerSubscriptionOut(BaseModel):
    id: str
    partner_id: str
    plan_code: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    billing_cycle: str
    commission_rate: Decimal | None = None
    features: dict | None = None
    created_at: datetime
    updated_at: datetime | None = None
    plan: PartnerPlanOut | None = None
