from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ProviderRefAuthorizeRequest(BaseModel):
    tx_id: str | None = None
    card_token: str
    station_id: str | None = None
    product_code: str | None = None
    amount: Decimal
    currency: str = Field(default="RUB")
    ts: datetime
    offline_mode_allowed: bool = Field(default=False)
    context: dict | None = None


class ProviderRefAuthorizeResponse(BaseModel):
    decision: str
    reason_code: str
    auth_code: str | None = None
    offline_profile: str | None = None
