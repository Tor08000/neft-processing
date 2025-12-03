from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ClientUser(BaseModel):
    id: str
    email: str
    role: str = "CLIENT_USER"
    organization_id: str
    organization_name: str | None = None


class ClientOperation(BaseModel):
    id: str
    date: datetime
    type: str
    status: str
    amount: int
    currency: str = "RUB"
    card_ref: str | None = None
    fuel_type: str | None = None


class ClientOperationsResponse(BaseModel):
    items: List[ClientOperation]
    total: int
    limit: int
    offset: int


class LimitItem(BaseModel):
    id: str
    type: str
    period: str
    amount: int
    used: int = 0
    remaining: int = Field(default=0, description="Оставшийся лимит")


class LimitsResponse(BaseModel):
    items: List[LimitItem]


class DashboardTotals(BaseModel):
    total_operations: int
    total_amount: int
    period: str
    active_limits: int
    spending_trend: List[int]
    dates: List[date]


class DashboardResponse(BaseModel):
    summary: DashboardTotals
    recent_operations: List[ClientOperation]
    limits: List[LimitItem]
