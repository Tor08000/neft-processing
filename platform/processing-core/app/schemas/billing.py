from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.operation import ProductType


class BillingSummaryItem(BaseModel):
    billing_date: date
    client_id: str | None
    merchant_id: str
    product_type: ProductType | None
    currency: str | None
    total_amount: int
    total_quantity: Decimal | None
    operations_count: int
    commission_amount: int

    model_config = ConfigDict(from_attributes=True)


class BillingSummaryPage(BaseModel):
    items: list[BillingSummaryItem]
    total: int
    limit: int
    offset: int
