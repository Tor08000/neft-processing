from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SettlementSummaryItem(BaseModel):
    settlement_period_id: str
    period_start: datetime
    period_end: datetime
    currency: str
    total_payments: int
    total_credits: int
    total_refunds: int
    total_net: int
    allocations_count: int

    model_config = ConfigDict(from_attributes=True)


class SettlementSummaryResponse(BaseModel):
    items: list[SettlementSummaryItem]
    total: int

    model_config = ConfigDict(from_attributes=True)
