from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Explain(BaseModel):
    primary_reason: str
    secondary: list[str] = Field(default_factory=list)
    confidence: float | None = None
    factors: list[str] = Field(default_factory=list)


class PointIn(BaseModel):
    lat: float
    lon: float
    ts: datetime


class VehicleIn(BaseModel):
    type: str
    fuel_type: str | None = None


class ContextIn(BaseModel):
    traffic: str | None = None
    weather: str | None = None


class EtaRequest(BaseModel):
    route_id: str
    points: list[PointIn]
    vehicle: VehicleIn
    context: ContextIn | None = None


class EtaResponse(BaseModel):
    eta_minutes: int
    confidence: float
    provider: str
    explain: Explain


class DeviationPoint(BaseModel):
    lat: float
    lon: float


class DeviationRequest(BaseModel):
    route_id: str
    planned_polyline: list[tuple[float, float]]
    actual_point: DeviationPoint
    threshold_meters: int


class DeviationResponse(BaseModel):
    deviation_meters: int
    is_violation: bool
    confidence: float
    provider: str
    explain: Explain


class ExplainRequest(BaseModel):
    kind: Literal["eta", "deviation"]
    context: dict[str, str] | None = None


class ExplainResponse(BaseModel):
    provider: str
    explain: Explain
