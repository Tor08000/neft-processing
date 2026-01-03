from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db import Base
from app.db.types import GUID, new_uuid_str


class MaintenanceItem(Base):
    __tablename__ = "maintenance_items"

    code = Column(String(64), primary_key=True)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    risk_level = Column(String(16), nullable=True)
    default_interval_km = Column(Numeric, nullable=True)
    default_interval_months = Column(Integer, nullable=True)


class MaintenanceRule(Base):
    __tablename__ = "maintenance_rules"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    brand = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)
    generation = Column(String(64), nullable=True)
    year_from = Column(Integer, nullable=True)
    year_to = Column(Integer, nullable=True)

    engine_type = Column(String(32), nullable=True)
    engine_volume_from = Column(Numeric, nullable=True)
    engine_volume_to = Column(Numeric, nullable=True)
    transmission = Column(String(16), nullable=True)
    drive_type = Column(String(16), nullable=True)

    item_code = Column(String(64), ForeignKey("maintenance_items.code"), nullable=False)

    interval_km = Column(Numeric, nullable=True)
    interval_months = Column(Integer, nullable=True)

    conditions = Column(JSONB, nullable=True)
    priority = Column(Integer, nullable=False, server_default="100")
    source = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaintenanceModifier(Base):
    __tablename__ = "maintenance_modifiers"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    item_code = Column(String(64), ForeignKey("maintenance_items.code"), nullable=False)
    condition_code = Column(String(32), nullable=False)
    factor = Column(Numeric, nullable=False)


class VehicleUsageProfile(Base):
    __tablename__ = "vehicle_usage_profile"

    vehicle_id = Column(GUID(), ForeignKey("vehicles.id"), primary_key=True)
    usage_type = Column(String(16), nullable=True)
    aggressiveness_score = Column(Numeric, nullable=True)
    heavy_load_flag = Column(Boolean, nullable=True)
    climate_zone = Column(String(16), nullable=True)
    avg_monthly_km = Column(Numeric, nullable=True)
    avg_consumption_l_100 = Column(Numeric, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class VehicleServiceRecord(Base):
    __tablename__ = "vehicle_service_records"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    vehicle_id = Column(GUID(), ForeignKey("vehicles.id"), nullable=False, index=True)
    item_code = Column(String(64), ForeignKey("maintenance_items.code"), nullable=False)
    service_at_km = Column(Numeric, nullable=True)
    service_at = Column(DateTime(timezone=True), nullable=True)
    partner_id = Column(GUID(), ForeignKey("partners.id"), nullable=True)
    order_id = Column(GUID(), nullable=True)
    note = Column(Text, nullable=True)
    source = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VehicleMaintenanceDismissal(Base):
    __tablename__ = "vehicle_maintenance_dismissals"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    vehicle_id = Column(GUID(), ForeignKey("vehicles.id"), nullable=False, index=True)
    item_code = Column(String(64), ForeignKey("maintenance_items.code"), nullable=False)
    dismissed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "MaintenanceItem",
    "MaintenanceModifier",
    "MaintenanceRule",
    "VehicleMaintenanceDismissal",
    "VehicleServiceRecord",
    "VehicleUsageProfile",
]
