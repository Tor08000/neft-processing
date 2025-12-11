from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.operations import OperationSchema
from app.models.operation import RiskResult


class AuthRequest(BaseModel):
    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str
    tariff_id: Optional[str] = None
    amount: int
    currency: str = "RUB"
    product_code: Optional[str] = None
    product_category: Optional[str] = None
    mcc: Optional[str] = None
    tx_type: Optional[str] = None
    client_group_id: Optional[str] = None
    card_group_id: Optional[str] = None


class AuthorizeRequest(BaseModel):
    client_id: str
    card_id: str
    terminal_id: str
    merchant_id: str
    tariff_id: Optional[str] = None
    product_id: Optional[str] = None
    product_type: Optional[str] = None
    amount: int
    currency: str = "RUB"
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    ext_operation_id: str
    product_category: Optional[str] = None
    tx_type: Optional[str] = None
    mcc: Optional[str] = None
    client_group_id: Optional[str] = None
    card_group_id: Optional[str] = None


class AuthorizeResponse(BaseModel):
    approved: bool
    operation_id: str
    status: str
    auth_code: Optional[str] = None
    response_code: str
    response_message: str
    risk_result: Optional[RiskResult] = None
    risk_score: Optional[float] = None
    limit_check_result: Optional[dict] = None


class CaptureRequest(BaseModel):
    amount: Optional[int] = None


class RefundRequest(BaseModel):
    amount: Optional[int] = None
    reason: Optional[str] = None


class CommitRequest(BaseModel):
    operation_id: str
    amount: Optional[int] = None
    quantity: Optional[float] = None


class ReverseRequest(BaseModel):
    operation_id: str
    reason: Optional[str] = None


class RefundOperationRequest(BaseModel):
    operation_id: str
    amount: int
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
    captured_amount: int = 0
    refunded_amount: int = 0

    authorized: bool
    response_code: str
    response_message: str

    reason: Optional[str] = None

    daily_limit: Optional[int] = None
    limit_per_tx: Optional[int] = None

    used_today: Optional[int] = None
    new_used_today: Optional[int] = None

    parent_operation_id: Optional[str] = None

    mcc: Optional[str] = None
    product_code: Optional[str] = None
    product_category: Optional[str] = None
    tx_type: Optional[str] = None

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

    mcc: str | None = None
    product_code: str | None = None
    product_category: str | None = None
    tx_type: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TransactionsPage(BaseModel):
    items: List[TransactionSchema]
    total: int
    limit: int
    offset: int


class TransactionDetailResponse(BaseModel):
    transaction: TransactionSchema
    operations: List[OperationSchema]
