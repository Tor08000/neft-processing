from __future__ import annotations

from pydantic import BaseModel

from neft_logistics_service.schemas.common import ProviderEnvelope


class FuelConsumptionRequest(BaseModel):
    trip_id: str
    distance_km: float
    vehicle_kind: str = "truck"
    idempotency_key: str | None = None


class FuelConsumptionResponse(ProviderEnvelope):
    trip_id: str
    liters: float
    method: str = "integration_hub"
    provider_mode: str | None = None
    sandbox_proof: dict | None = None
    last_attempt: dict | None = None
    retryable: bool | None = None
    idempotency_key: str | None = None
    idempotency_status: str | None = None
