# services/core-api/app/schemas/operations.py
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class OperationBase(BaseModel):
    operation_id: str
    created_at: datetime

    operation_type: str  # AUTH / CAPTURE / REFUND / REVERSAL
    status: str          # AUTHORIZED / CAPTURED / REFUNDED / REVERSED / DECLINED

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

    class Config:
        orm_mode = True


class OperationRead(OperationBase):
    """Ответ для одного объекта операции."""
    pass


class OperationListItem(OperationBase):
    """Элемент списка операций."""
    pass


class OperationListResponse(BaseModel):
    items: List[OperationListItem]
    total: int
    limit: int
    offset: int
