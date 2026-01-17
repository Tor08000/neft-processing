from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class MoneyAmount(BaseModel):
    amount: Decimal
    currency: str


class RevenuePlanMixItem(BaseModel):
    plan: str
    orgs: int
    mrr: Decimal | None = None


class RevenueAddonMixItem(BaseModel):
    addon: str
    orgs: int
    mrr: Decimal


class RevenueSummaryResponse(BaseModel):
    as_of: date
    mrr: MoneyAmount
    arr: MoneyAmount
    active_orgs: int
    overdue_orgs: int
    overdue_amount: Decimal
    usage_revenue_mtd: Decimal
    plan_mix: list[RevenuePlanMixItem]
    addon_mix: list[RevenueAddonMixItem]
    overdue_buckets: list["RevenueOverdueBucket"]


class RevenueOverdueBucket(BaseModel):
    bucket: str
    label: str
    orgs: int
    amount: Decimal


class RevenueOverdueItem(BaseModel):
    org_id: int
    org_name: str | None = None
    invoice_id: str
    due_at: datetime | None = None
    overdue_days: int
    amount: Decimal
    currency: str | None = None
    subscription_plan: str | None = None
    subscription_status: str | None = None


class RevenueOverdueResponse(BaseModel):
    items: list[RevenueOverdueItem]
    total: int
    limit: int
    offset: int


class RevenueUsageMeterItem(BaseModel):
    ref_code: str | None = None
    quantity: Decimal
    amount: Decimal


class RevenueUsageResponse(BaseModel):
    period_from: date
    period_to: date
    meters: list[RevenueUsageMeterItem]
