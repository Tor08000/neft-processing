from __future__ import annotations

from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class FleetVehicleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class FleetVehicle(Base):
    __tablename__ = "fleet_vehicles"
    __table_args__ = (
        UniqueConstraint("client_id", "plate_number", name="uq_fleet_vehicle_plate_client"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    plate_number = Column(String(32), nullable=False)
    vin = Column(String(64), nullable=True)
    brand = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)
    fuel_type_preferred = Column(String(32), nullable=True)
    tank_capacity_liters = Column(BigInteger, nullable=True)
    status = Column(ExistingEnum(FleetVehicleStatus, name="fleet_vehicle_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FleetDriverStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class FleetDriver(Base):
    __tablename__ = "fleet_drivers"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    phone = Column(String(32), nullable=True)
    status = Column(ExistingEnum(FleetDriverStatus, name="fleet_driver_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["FleetDriver", "FleetDriverStatus", "FleetVehicle", "FleetVehicleStatus"]
