from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IntakeAuthorizeRequest(BaseModel):
    external_partner_id: str
    azs_id: Optional[str] = None
    terminal_id: Optional[str] = None
    product_id: Optional[str] = None
    liters: Optional[float] = None
    amount: int = Field(..., ge=0)
    currency: str = "RUB"
    timestamp: datetime
    card_identifier: str
    geo_location: Optional[dict] = None
    simulate_posting_error: bool = False


class IntakeRefundRequest(BaseModel):
    external_partner_id: str
    operation_id: str
    amount: Optional[int] = None
    reason: Optional[str] = None


class IntakeReversalRequest(BaseModel):
    external_partner_id: str
    operation_id: str
    reason: Optional[str] = None


class IntakeCallbackRequest(BaseModel):
    operation_id: str
    status: str
    payload: dict | None = None


class IntakeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    operation_id: str
    posting_status: str
    risk_code: Optional[str] = None
    limit_code: Optional[str] = None
    response_code: Optional[str] = None
