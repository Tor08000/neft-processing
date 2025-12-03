from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AuthorizeRequest(BaseModel):
    card_token: str = Field(..., description="Внутренний токен карты")
    amount: float = Field(..., gt=0)
    currency: str = "RUB"
    product_code: Optional[str] = None
    ext_id: Optional[str] = None


class AuthorizeResponse(BaseModel):
    approved: bool
    trans_id: Optional[int] = None
    hold_id: Optional[int] = None
    reason: Optional[str] = None


class CaptureRequest(BaseModel):
    trans_id: int
    amount: Optional[float] = None  # по умолчанию на всю сумму холда


class ReverseRequest(BaseModel):
    trans_id: int
    reason: Optional[str] = None


class TxnStatus(BaseModel):
    id: int
    status: str
    type: str
    amount: float
    currency: str
    meta: Dict[str, Any] = {}
