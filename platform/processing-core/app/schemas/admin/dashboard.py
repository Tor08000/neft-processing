from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ClientShort(BaseModel):
    client_id: str
    name: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime


class ClientListResponse(BaseModel):
    items: List[ClientShort]
    total: int
    limit: int
    offset: int


class CardShort(BaseModel):
    card_id: str
    client_id: str
    status: Optional[str] = None
    active: Optional[bool] = None
    created_at: datetime


class CardListResponse(BaseModel):
    items: List[CardShort]
    total: int
    limit: int
    offset: int


class OperationShort(BaseModel):
    operation_id: str
    created_at: datetime
    operation_type: str
    status: str
    merchant_id: Optional[str] = None
    terminal_id: Optional[str] = None
    client_id: Optional[str] = None
    card_id: Optional[str] = None
    amount: int
    currency: str
    captured_amount: int = 0
    refunded_amount: int = 0
    parent_operation_id: Optional[str] = None
    mcc: Optional[str] = None
    product_code: Optional[str] = None
    product_category: Optional[str] = None
    tx_type: Optional[str] = None
    daily_limit: Optional[int] = None
    limit_per_tx: Optional[int] = None
    used_today: Optional[int] = None
    new_used_today: Optional[int] = None
    authorized: Optional[bool] = None
    response_code: Optional[str] = None
    response_message: Optional[str] = None
    reason: Optional[str] = None
    risk_result: Optional[str] = None
    risk_score: Optional[float] = None
    risk_reasons: Optional[List[str]] = None
    risk_flags: Optional[dict] = None
    risk_source: Optional[str] = None
    risk_rules_fired: Optional[List[str]] = None


class OperationListResponse(BaseModel):
    items: List[OperationShort]
    total: int
    limit: int
    offset: int


class TransactionShort(BaseModel):
    transaction_id: str
    created_at: datetime
    updated_at: datetime
    client_id: Optional[str] = None
    card_id: Optional[str] = None
    merchant_id: Optional[str] = None
    terminal_id: Optional[str] = None
    status: str
    authorized_amount: int
    captured_amount: int
    refunded_amount: int
    currency: str
    mcc: Optional[str] = None
    product_category: Optional[str] = None
    tx_type: Optional[str] = None


class TransactionListResponse(BaseModel):
    items: List[TransactionShort]
    total: int
    limit: int
    offset: int
