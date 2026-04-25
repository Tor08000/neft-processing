from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from neft_logistics_service.schemas.legacy import ContextIn, VehicleIn


class RoutePreviewPoint(BaseModel):
    lat: float
    lon: float
    sequence: int | None = None
    stop_id: str | None = None


class RoutePreviewRequest(BaseModel):
    route_id: str
    points: list[RoutePreviewPoint] = Field(min_length=2)
    vehicle: VehicleIn
    context: ContextIn | None = None


class RoutePreviewGeometryPoint(BaseModel):
    lat: float
    lon: float


class RoutePreviewResponse(BaseModel):
    provider: str
    geometry: list[RoutePreviewGeometryPoint]
    distance_km: float
    eta_minutes: int
    confidence: float
    computed_at: datetime
    degraded: bool
    degradation_reason: str | None = None
