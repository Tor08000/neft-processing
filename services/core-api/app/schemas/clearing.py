from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ClearingBatchOperationOut(BaseModel):
    id: UUID
    operation_id: str
    amount: int

    model_config = ConfigDict(from_attributes=True)


class ClearingBatchOut(BaseModel):
    id: UUID
    merchant_id: str
    date_from: date
    date_to: date
    total_amount: int
    operations_count: int
    status: str
    created_at: datetime
    updated_at: datetime
    operations: Optional[List[ClearingBatchOperationOut]] = None

    model_config = ConfigDict(from_attributes=True)


class BuildBatchRequest(BaseModel):
    date_from: date
    date_to: date
    merchant_id: str
