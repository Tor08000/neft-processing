from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.vehicle_profile import (
    VehicleEngineType,
    VehicleMileageSource,
    VehicleOdometerSource,
    VehicleRecommendationStatus,
    VehicleServiceType,
    VehicleUsageType,
)


class VehicleBase(BaseModel):
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    engine_type: VehicleEngineType | None = None
    engine_volume: Decimal | None = None
    fuel_type: str | None = None
    vin: str | None = None
    plate_number: str | None = None
    avg_consumption_l_per_100km: Decimal | None = None
    usage_type: VehicleUsageType | None = None


class VehicleCreate(VehicleBase):
    start_odometer_km: Decimal = Field(..., ge=0)
    current_odometer_km: Decimal | None = Field(default=None, ge=0)


class VehicleUpdate(VehicleBase):
    current_odometer_km: Decimal | None = Field(default=None, ge=0)
    start_odometer_km: Decimal | None = Field(default=None, ge=0)


class VehicleOut(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    start_odometer_km: Decimal
    current_odometer_km: Decimal
    odometer_source: VehicleOdometerSource
    created_at: datetime
    updated_at: datetime


class VehicleListResponse(BaseModel):
    items: list[VehicleOut]


class VehicleMileageOut(BaseModel):
    current_odometer_km: Decimal
    odometer_source: VehicleOdometerSource
    avg_consumption_l_per_100km: Decimal | None = None


class VehicleMileageEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: VehicleMileageSource
    fuel_txn_id: str | None = None
    liters: Decimal | None = None
    estimated_km: Decimal | None = None
    odometer_before: Decimal
    odometer_after: Decimal
    created_at: datetime


class VehicleMileageEventsResponse(BaseModel):
    items: list[VehicleMileageEventOut]
    total: int
    limit: int
    offset: int


class VehicleRecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    service_type: VehicleServiceType
    recommended_at_km: Decimal
    current_km: Decimal
    status: VehicleRecommendationStatus
    reason: str
    partner_id: str | None = None
    created_at: datetime


class VehicleRecommendationsResponse(BaseModel):
    items: list[VehicleRecommendationOut]
