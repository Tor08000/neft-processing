from datetime import datetime
from typing import List, Literal, Optional
from datetime import datetime
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict

GroupBy = Literal["client", "card", "merchant", "terminal", "station"]


class TurnoverGroupKey(BaseModel):
    client_id: Optional[str] = None
    card_id: Optional[str] = None
    merchant_id: Optional[str] = None
    terminal_id: Optional[str] = None

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


class BillingDailyReportItem(BaseModel):
    date: date
    merchant_id: str
    total_captured_amount: int
    total_operations: int


class BillingSummaryItem(BaseModel):
    date: date
    merchant_id: str
    total_captured_amount: int
    operations_count: int
    status: str | None = None
    generated_at: datetime | None = None
    finalized_at: datetime | None = None
    id: str | None = None
    hash: str | None = None
