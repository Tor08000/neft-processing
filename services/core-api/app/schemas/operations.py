from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class OperationSchema(BaseModel):
    operation_id: str
    created_at: datetime
    operation_type: str
    status: str

    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str

    amount: int
    currency: str = "RUB"
    captured_amount: int = 0
    refunded_amount: int = 0

    daily_limit: Optional[int] = None
    limit_per_tx: Optional[int] = None
    used_today: Optional[int] = None
    new_used_today: Optional[int] = None

    authorized: bool = False
    response_code: str = "00"
    response_message: str = "OK"

    parent_operation_id: Optional[str] = None
    reason: Optional[str] = None

    mcc: Optional[str] = None
    product_code: Optional[str] = None
    product_category: Optional[str] = None
    tx_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OperationsPage(BaseModel):
    items: List[OperationSchema]
    total: int
    limit: int
    offset: int


class OperationTimeline(BaseModel):
    root: OperationSchema
    children: List[OperationSchema]


# Удобный псевдоним для журнала транзакций
TransactionLogPage = OperationsPage
