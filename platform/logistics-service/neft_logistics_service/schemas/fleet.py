from __future__ import annotations

from pydantic import BaseModel, Field

from neft_logistics_service.schemas.common import IdempotentResponse, ProviderEnvelope


class FleetVehicle(BaseModel):
    vehicle_id: str
    plate_number: str
    kind: str = "truck"
    status: str = "active"


class FleetListRequest(BaseModel):
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class FleetListResponse(ProviderEnvelope):
    items: list[FleetVehicle] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class FleetUpsertRequest(BaseModel):
    vehicle_id: str
    plate_number: str
    kind: str = "truck"
    status: str = "active"


class FleetUpsertResponse(ProviderEnvelope, IdempotentResponse):
    vehicle: FleetVehicle
