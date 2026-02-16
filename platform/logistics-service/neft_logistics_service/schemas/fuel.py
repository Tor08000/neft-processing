from __future__ import annotations

from pydantic import BaseModel

from neft_logistics_service.schemas.common import ProviderEnvelope


class FuelConsumptionRequest(BaseModel):
    trip_id: str
    distance_km: float
    vehicle_kind: str = "truck"


class FuelConsumptionResponse(ProviderEnvelope):
    trip_id: str
    liters: float
    method: str = "integration_hub"
