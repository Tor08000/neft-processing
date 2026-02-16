from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from neft_logistics_service.schemas.common import IdempotentResponse, ProviderEnvelope


class TripCreateRequest(BaseModel):
    trip_id: str
    vehicle_id: str
    route_id: str
    starts_at: datetime | None = None


class TripCreateResponse(ProviderEnvelope, IdempotentResponse):
    trip_id: str
    status: str = "created"


class TripStatusResponse(ProviderEnvelope):
    trip_id: str
    status: str
    updated_at: datetime | None = None
