from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.operations import OperationSchema


class AuthRequest(BaseModel):
    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str
    amount: int
    currency: str = "RUB"


class CaptureRequest(BaseModel):
    amount: int


class RefundRequest(BaseModel):
    amount: Optional[int] = None
    reason: Optional[str] = None


class ReversalRequest(BaseModel):
    reason: Optional[str] = None


class OperationBase(BaseModel):
    operation_id: str
    created_at: datetime

    operation_type: str  # AUTH / CAPTURE / REFUND / REVERSAL
    status: str  # AUTHORIZED / CAPTURED / REFUNDED / REVERSED / DECLINED

    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str

    amount: int
    currency: str

    authorized: bool
    response_code: str
    response_message: str

    reason: Optional[str] = None

    daily_limit: Optional[int] = None
    limit_per_tx: Optional[int] = None

    used_today: Optional[int] = None
    new_used_today: Optional[int] = None

    parent_operation_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OperationRead(OperationBase):
    """Ответ для одного объекта операции."""


class OperationListItem(OperationBase):
    """Элемент списка операций."""


class OperationListResponse(BaseModel):
    items: List[OperationListItem]
    total: int
    limit: int
    offset: int


class TransactionSchema(BaseModel):
    transaction_id: str
    created_at: datetime
    updated_at: datetime

    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str

    currency: str
    authorized_amount: int
    captured_amount: int
    refunded_amount: int

    status: str

    operation_types: List[str]
    auth_operation: OperationSchema
    last_operation: OperationSchema

    model_config = ConfigDict(from_attributes=True)


class TransactionsPage(BaseModel):
    items: List[TransactionSchema]
    total: int
    limit: int
    offset: int


class TransactionDetailResponse(BaseModel):
    transaction: TransactionSchema
    operations: List[OperationSchema]
