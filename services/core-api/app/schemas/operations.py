# services/core-api/app/schemas/operations.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class OperationBase(BaseModel):
    """
    Базовая схема операции из журнала.

    ВАЖНО:
    - operation_id хранится в БД как строка (VARCHAR(64)),
      поэтому здесь тоже используем str.
    """
    operation_id: str
    created_at: datetime

    operation_type: str
    status: str

    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str

    amount: int
    currency: str

    daily_limit: Optional[int] = None
    limit_per_tx: Optional[int] = None
    used_today: Optional[int] = None
    new_used_today: Optional[int] = None

    authorized: bool

    response_code: Optional[str] = None
    response_message: Optional[str] = None

    parent_operation_id: Optional[str] = None
    reason: Optional[str] = None

    class Config:
        # позволяем создавать схему из ORM-объекта SQLAlchemy
        orm_mode = True


class OperationRead(OperationBase):
    """Схема для отдачи одной операции наружу."""
    pass


class OperationList(BaseModel):
    """Список операций с пагинацией."""
    items: List[OperationRead]
    total: int
    limit: int
    offset: int
