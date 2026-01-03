from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, root_validator


CampaignStatus = Literal["DRAFT", "ACTIVE", "PAUSED", "ENDED", "EXHAUSTED"]
CampaignObjective = Literal["CPC", "CPA"]
SponsoredEventType = Literal["IMPRESSION", "CLICK", "CONVERSION"]
SpendDirection = Literal["DEBIT", "CREDIT"]


class SponsoredCampaignCreate(BaseModel):
    title: str
    objective: CampaignObjective
    targeting: dict = Field(default_factory=dict)
    scope: dict
    bid: Decimal
    daily_cap: Decimal | None = None
    total_budget: Decimal
    starts_at: datetime
    ends_at: datetime | None = None

    @root_validator(skip_on_failure=True)
    def _validate_budget(cls, values: dict) -> dict:
        bid = values.get("bid")
        total_budget = values.get("total_budget")
        if bid is not None and bid <= 0:
            raise ValueError("bid_must_be_positive")
        if total_budget is not None and total_budget <= 0:
            raise ValueError("total_budget_must_be_positive")
        daily_cap = values.get("daily_cap")
        if daily_cap is not None and daily_cap <= 0:
            raise ValueError("daily_cap_must_be_positive")
        return values


class SponsoredCampaignUpdate(BaseModel):
    title: str | None = None
    targeting: dict | None = None
    scope: dict | None = None
    bid: Decimal | None = None
    daily_cap: Decimal | None = None
    total_budget: Decimal | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @root_validator(skip_on_failure=True)
    def _validate_budget(cls, values: dict) -> dict:
        bid = values.get("bid")
        if bid is not None and bid <= 0:
            raise ValueError("bid_must_be_positive")
        total_budget = values.get("total_budget")
        if total_budget is not None and total_budget <= 0:
            raise ValueError("total_budget_must_be_positive")
        daily_cap = values.get("daily_cap")
        if daily_cap is not None and daily_cap <= 0:
            raise ValueError("daily_cap_must_be_positive")
        return values


class SponsoredCampaignOut(BaseModel):
    id: str
    tenant_id: str
    partner_id: str
    title: str
    status: CampaignStatus
    objective: CampaignObjective
    currency: str
    targeting: dict
    scope: dict
    bid: Decimal
    daily_cap: Decimal | None = None
    total_budget: Decimal
    spent_budget: Decimal
    starts_at: datetime
    ends_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SponsoredCampaignListResponse(BaseModel):
    items: list[SponsoredCampaignOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class SponsoredCampaignStatusUpdate(BaseModel):
    status: CampaignStatus
    reason: str | None = None


class SponsoredEventCreate(BaseModel):
    campaign_id: str
    product_id: str | None = None
    event_type: SponsoredEventType
    context: dict = Field(default_factory=dict)
    meta: dict | None = None


class SponsoredEventOut(BaseModel):
    id: str
    campaign_id: str
    partner_id: str
    client_id: str | None = None
    user_id: str | None = None
    product_id: str | None = None
    event_type: SponsoredEventType
    event_ts: datetime
    context: dict
    meta: dict | None = None


class SponsoredCampaignStatsOut(BaseModel):
    impressions: int
    clicks: int
    conversions: int
    spend: Decimal


class SponsoredChargeRequest(BaseModel):
    order_id: str
    paid_amount: Decimal
    paid_currency: str = "RUB"


class SponsoredRefundRequest(BaseModel):
    order_id: str
    refunded_amount: Decimal
    paid_amount: Decimal
    currency: str = "RUB"


class SponsoredLedgerEntryOut(BaseModel):
    id: str
    campaign_id: str
    partner_id: str
    spend_type: str
    amount: Decimal
    currency: str
    ref_type: str
    ref_id: str
    direction: SpendDirection
    reversal_of: str | None = None
    created_at: datetime
