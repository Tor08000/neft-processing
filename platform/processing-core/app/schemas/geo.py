from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel


class GeoMetricEnum(str, Enum):
    TX_COUNT = "tx_count"
    AMOUNT_SUM = "amount_sum"
    DECLINED_COUNT = "declined_count"
    CAPTURED_COUNT = "captured_count"
    RISK_RED_COUNT = "risk_red_count"


class GeoStationMetricsItem(BaseModel):
    station_id: str
    station_name: str | None = None
    station_address: str | None = None
    lat: float | None = None
    lon: float | None = None
    tx_count: int
    captured_count: int
    declined_count: int
    amount_sum: float
    liters_sum: float
    risk_red_count: int
    risk_yellow_count: int


class GeoStationsMetricsResponse(BaseModel):
    date_from: date
    date_to: date
    metric: GeoMetricEnum
    items: list[GeoStationMetricsItem]
    limit: int
