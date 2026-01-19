from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SettlementSnapshotOut(BaseModel):
    settlement_snapshot_id: str
    settlement_id: str
    order_id: str
    gross_amount: Decimal
    platform_fee: Decimal
    penalties: Decimal
    partner_net: Decimal
    currency: str
    finalized_at: datetime | None = None
    hash: str | None = None


class SettlementOverrideIn(BaseModel):
    gross_amount: Decimal
    platform_fee: Decimal
    penalties: Decimal
    partner_net: Decimal
    currency: str = Field(default="RUB")
    reason: str
