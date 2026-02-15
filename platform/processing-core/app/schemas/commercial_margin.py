from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel


class MarginSortBy(str, Enum):
    GROSS_MARGIN = "gross_margin"
    MARGIN_PCT = "margin_pct"
    REVENUE_SUM = "revenue_sum"
    COST_SUM = "cost_sum"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class StationMarginItem(BaseModel):
    station_id: str
    station_name: str | None = None
    station_address: str | None = None
    lat: float | None = None
    lon: float | None = None
    revenue_sum: float
    cost_sum: float
    gross_margin: float
    margin_pct: float
    tx_count: int


class StationMarginResponse(BaseModel):
    date_from: date
    date_to: date
    sort_by: MarginSortBy
    order: SortOrder
    limit: int
    items: list[StationMarginItem]
