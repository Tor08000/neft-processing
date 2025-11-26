from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict

GroupBy = Literal[
    "client",
    "card",
    "merchant",
    "terminal",
    "station",
    "fuel_category",
    "mcc",
    "tx_type",
]


class TurnoverGroupKey(BaseModel):
    client_id: Optional[str] = None
    card_id: Optional[str] = None
    merchant_id: Optional[str] = None
    terminal_id: Optional[str] = None

    product_category: Optional[str] = None
    mcc: Optional[str] = None
    tx_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TurnoverItem(BaseModel):
    group_key: TurnoverGroupKey

    transaction_count: int

    authorized_amount: int
    captured_amount: int
    refunded_amount: int
    net_turnover: int  # captured - refunded

    currency: str = "RUB"


class TurnoverTotals(BaseModel):
    transaction_count: int
    authorized_amount: int
    captured_amount: int
    refunded_amount: int
    net_turnover: int
    currency: str = "RUB"


class TurnoverReportResponse(BaseModel):
    items: List[TurnoverItem]
    totals: TurnoverTotals

    group_by: GroupBy
    from_created_at: datetime
    to_created_at: datetime
