from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)

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

class EmployeeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INVITED = "INVITED"
    DISABLED = "DISABLED"


class FuelGroupRole(str, Enum):
    VIEWER = "viewer"
    MANAGER = "manager"
    ADMIN = "admin"


class FuelCardGroupMember(Base):
    __tablename__ = "fuel_card_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "card_id", name="pk_fuel_card_group_members"),
    )

    group_id = Column(String(36), ForeignKey("fuel_card_groups.id"), primary_key=True)
    card_id = Column(String(36), ForeignKey("fuel_cards.id"), primary_key=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    removed_at = Column(DateTime(timezone=True), nullable=True)
    audit_event_id = Column(String(36), nullable=True)


class ClientEmployee(Base):
    __tablename__ = "client_employees"
    __table_args__ = (
        UniqueConstraint("client_id", "email", name="uq_client_employees_client_email"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    email = Column(String(256), nullable=False)
    status = Column(ExistingEnum(EmployeeStatus, name="employee_status"), nullable=False)
    timezone = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit_event_id = Column(String(36), nullable=True)


class FuelGroupAccess(Base):
    __tablename__ = "fuel_group_access"
    __table_args__ = (
        UniqueConstraint("group_id", "employee_id", name="uq_fuel_group_access_group_employee"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("fuel_card_groups.id"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("client_employees.id"), nullable=False, index=True)
    role = Column(ExistingEnum(FuelGroupRole, name="fuel_group_role"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    audit_event_id = Column(String(36), nullable=True)


__all__ = [
    "ClientEmployee",
    "EmployeeStatus",
    "FleetDriver",
    "FleetDriverStatus",
    "FleetVehicle",
    "FleetVehicleStatus",
    "FuelCardGroupMember",
    "FuelGroupAccess",
    "FuelGroupRole",
]
