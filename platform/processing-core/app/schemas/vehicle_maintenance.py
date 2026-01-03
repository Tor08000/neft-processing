from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VehicleUsageProfileUpdate(BaseModel):
    usage_type: str | None = None
    aggressiveness_score: Decimal | None = Field(default=None, ge=0, le=1)
    heavy_load_flag: bool | None = None
    climate_zone: str | None = None
    avg_monthly_km: Decimal | None = Field(default=None, ge=0)
    avg_consumption_l_100: Decimal | None = Field(default=None, ge=0)


class VehicleUsageProfileOut(VehicleUsageProfileUpdate):
    model_config = ConfigDict(from_attributes=True)

    vehicle_id: str
    updated_at: datetime


class VehicleServiceRecordCreate(BaseModel):
    item_code: str
    service_at_km: Decimal | None = Field(default=None, ge=0)
    service_at: datetime | None = None
    partner_id: str | None = None
    order_id: str | None = None
    note: str | None = None
    source: str = "MANUAL"


class VehicleServiceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vehicle_id: str
    item_code: str
    service_at_km: Decimal | None = None
    service_at: datetime | None = None
    partner_id: str | None = None
    order_id: str | None = None
    note: str | None = None
    source: str
    created_at: datetime


class VehicleServiceRecordsResponse(BaseModel):
    items: list[VehicleServiceRecordOut]
    total: int
    limit: int
    offset: int


class MaintenanceRecommendationOut(BaseModel):
    item_code: str
    title: str
    status: str
    interval_km: Decimal | None = None
    interval_months: int | None = None
    effective_interval_km: Decimal | None = None
    effective_interval_months: int | None = None
    last_service_km: Decimal | None = None
    last_service_at: datetime | None = None
    current_km: Decimal
    due_km: Decimal | None = None
    due_in_km: Decimal | None = None
    overdue_km: Decimal | None = None
    due_at: datetime | None = None
    due_in_months: int | None = None
    explain: str


class MaintenanceRecommendationsResponse(BaseModel):
    items: list[MaintenanceRecommendationOut]
