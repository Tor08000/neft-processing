from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ElasticitySortBy(str, Enum):
    ELASTICITY_ABS = "elasticity_abs"
    CONFIDENCE = "confidence_score"
    ELASTICITY_SCORE = "elasticity_score"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class StationElasticityItem(BaseModel):
    station_id: str
    station_name: str | None = None
    station_address: str | None = None
    lat: float | None = None
    lon: float | None = None
    product_code: str
    window_days: int
    elasticity_score: float
    elasticity_abs: float
    confidence_score: float
    sample_points: int
    total_volume: float
    notes: str
    updated_at: datetime | None = None


class StationElasticityListResponse(BaseModel):
    window_days: int
    sort_by: ElasticitySortBy
    order: SortOrder
    limit: int
    items: list[StationElasticityItem]


class StationElasticityDetailResponse(BaseModel):
    station_id: str
    window_days: int
    items: list[StationElasticityItem]
