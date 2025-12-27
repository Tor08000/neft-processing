from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.fleet import FleetDriverStatus, FleetVehicleStatus
from app.models.fuel import FuelCardStatus, FuelLimitPeriod, FuelLimitScopeType, FuelLimitType


class VehicleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int
    client_id: str
    plate_number: str
    vin: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    fuel_type_preferred: Optional[str] = None
    tank_capacity_liters: Optional[int] = None
    status: FleetVehicleStatus = FleetVehicleStatus.ACTIVE


class VehicleOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    plate_number: str
    vin: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    fuel_type_preferred: Optional[str] = None
    tank_capacity_liters: Optional[int] = None
    status: FleetVehicleStatus
    created_at: datetime


class DriverCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int
    client_id: str
    full_name: str
    phone: Optional[str] = None
    status: FleetDriverStatus = FleetDriverStatus.ACTIVE


class DriverOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    full_name: str
    phone: Optional[str] = None
    status: FleetDriverStatus
    created_at: datetime


class CardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int
    client_id: str
    card_token: str
    status: FuelCardStatus = FuelCardStatus.ACTIVE
    card_group_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    driver_id: Optional[str] = None
    issued_at: Optional[datetime] = None
    blocked_at: Optional[datetime] = None
    meta: Optional[dict] = None


class CardOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    card_token: str
    status: FuelCardStatus
    card_group_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    driver_id: Optional[str] = None
    issued_at: Optional[datetime] = None
    blocked_at: Optional[datetime] = None
    meta: Optional[dict] = None
    created_at: datetime


class LimitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int
    client_id: str
    scope_type: FuelLimitScopeType
    scope_id: Optional[str] = None
    limit_type: FuelLimitType
    period: FuelLimitPeriod
    value: int
    currency: Optional[str] = None
    priority: int = 100
    active: bool = True
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    meta: Optional[dict] = None


class LimitOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    scope_type: FuelLimitScopeType
    scope_id: Optional[str] = None
    limit_type: FuelLimitType
    period: FuelLimitPeriod
    value: int
    currency: Optional[str] = None
    priority: int
    active: bool
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    meta: Optional[dict] = None
    created_at: datetime


__all__ = [
    "CardCreate",
    "CardOut",
    "DriverCreate",
    "DriverOut",
    "LimitCreate",
    "LimitOut",
    "VehicleCreate",
    "VehicleOut",
]
