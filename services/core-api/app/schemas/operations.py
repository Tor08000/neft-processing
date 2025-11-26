from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class OperationOut(BaseModel):
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

    daily_limit: Optional[int] = None
    limit_per_tx: Optional[int] = None
    used_today: Optional[int] = None
    new_used_today: Optional[int] = None

    authorized: bool = False
    response_code: str = "00"
    response_message: str = "OK"

    parent_operation_id: Optional[str] = None
    reason: Optional[str] = None

    class Config:
        # для Pydantic 1.x
        orm_mode = True
        # для Pydantic 2.x
        from_attributes = True


class OperationsPage(BaseModel):
    items: List[OperationOut]
    total: int
    limit: int
    offset: int
