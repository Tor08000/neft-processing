from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class VehicleEngineType(str, Enum):
    PETROL = "petrol"
    DIESEL = "diesel"
    HYBRID = "hybrid"
    ELECTRIC = "electric"


class VehicleOdometerSource(str, Enum):
    MANUAL = "MANUAL"
    ESTIMATED = "ESTIMATED"
    MIXED = "MIXED"


class VehicleUsageType(str, Enum):
    CITY = "city"
    HIGHWAY = "highway"
    MIXED = "mixed"
    AGGRESSIVE = "aggressive"


class VehicleMileageSource(str, Enum):
    FUEL_TXN = "FUEL_TXN"
    MANUAL_UPDATE = "MANUAL_UPDATE"
    SERVICE_EVENT = "SERVICE_EVENT"


class VehicleRecommendationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACCEPTED = "ACCEPTED"
    DONE = "DONE"
    DISMISSED = "DISMISSED"


class VehicleServiceType(str, Enum):
    OIL_CHANGE = "OIL_CHANGE"
    FILTERS = "FILTERS"
    BRAKES = "BRAKES"
    TIMING = "TIMING"
    OTHER = "OTHER"


class VehicleProfile(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("client_id", "plate_number", name="uq_vehicle_plate_client"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)

    brand = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)
    generation = Column(String(64), nullable=True)
    year = Column(Integer, nullable=True)
    engine_type = Column(ExistingEnum(VehicleEngineType, name="vehicle_engine_type"), nullable=True)
    engine_volume = Column(Numeric, nullable=True)
    fuel_type = Column(String(32), nullable=True)
    transmission = Column(String(16), nullable=True)
    drive_type = Column(String(16), nullable=True)
    vin = Column(String(64), nullable=True)
    plate_number = Column(String(32), nullable=True)

    start_odometer_km = Column(Numeric, nullable=False)
    current_odometer_km = Column(Numeric, nullable=False)
    odometer_source = Column(
        ExistingEnum(VehicleOdometerSource, name="vehicle_odometer_source"),
        nullable=False,
    )

    avg_consumption_l_per_100km = Column(Numeric, nullable=True)
    usage_type = Column(ExistingEnum(VehicleUsageType, name="vehicle_usage_type"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class VehicleCardLink(Base):
    __tablename__ = "vehicle_cards"
    __table_args__ = (
        UniqueConstraint("vehicle_id", "card_id", name="pk_vehicle_cards"),
    )

    vehicle_id = Column(GUID(), ForeignKey("vehicles.id"), primary_key=True)
    card_id = Column(GUID(), ForeignKey("fuel_cards.id"), primary_key=True)
    linked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VehicleMileageEvent(Base):
    __tablename__ = "vehicle_mileage_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    vehicle_id = Column(GUID(), ForeignKey("vehicles.id"), nullable=False, index=True)
    source = Column(ExistingEnum(VehicleMileageSource, name="vehicle_mileage_source"), nullable=False)
    fuel_txn_id = Column(GUID(), ForeignKey("fuel_transactions.id"), nullable=True, index=True)
    liters = Column(Numeric, nullable=True)
    estimated_km = Column(Numeric, nullable=True)
    odometer_before = Column(Numeric, nullable=False)
    odometer_after = Column(Numeric, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ServiceInterval(Base):
    __tablename__ = "service_intervals"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    brand = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)
    engine_type = Column(ExistingEnum(VehicleEngineType, name="vehicle_engine_type"), nullable=True)
    service_type = Column(ExistingEnum(VehicleServiceType, name="vehicle_service_type"), nullable=False)
    interval_km = Column(Numeric, nullable=False)
    interval_months = Column(Integer, nullable=True)
    description = Column(String(256), nullable=True)


class VehicleRecommendation(Base):
    __tablename__ = "vehicle_recommendations"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    vehicle_id = Column(GUID(), ForeignKey("vehicles.id"), nullable=False, index=True)
    service_type = Column(ExistingEnum(VehicleServiceType, name="vehicle_service_type"), nullable=False)
    recommended_at_km = Column(Numeric, nullable=False)
    current_km = Column(Numeric, nullable=False)
    status = Column(
        ExistingEnum(VehicleRecommendationStatus, name="vehicle_recommendation_status"),
        nullable=False,
    )
    reason = Column(String(512), nullable=False)
    partner_id = Column(GUID(), ForeignKey("partners.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "ServiceInterval",
    "VehicleCardLink",
    "VehicleEngineType",
    "VehicleMileageEvent",
    "VehicleMileageSource",
    "VehicleOdometerSource",
    "VehicleProfile",
    "VehicleRecommendation",
    "VehicleRecommendationStatus",
    "VehicleServiceType",
    "VehicleUsageType",
]
