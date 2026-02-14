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
    RISK_YELLOW_COUNT = "risk_yellow_count"


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


class GeoBBox(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


class GeoTilesItem(BaseModel):
    tile_x: int
    tile_y: int
    value: float | int


class GeoTilesResponse(BaseModel):
    date_from: date
    date_to: date
    zoom: int
    metric: GeoMetricEnum
    bbox: GeoBBox
    items: list[GeoTilesItem]
    returned_tiles: int
    limit_tiles: int
