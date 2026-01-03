from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.models.vehicle_profile import VehicleServiceType


class VehicleServiceRecord(Base):
    __tablename__ = "vehicle_service_records"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=True, index=True)
    vehicle_id = Column(GUID(), ForeignKey("vehicles.id"), nullable=False, index=True)

    booking_id = Column(GUID(), ForeignKey("service_bookings.id", ondelete="RESTRICT"), nullable=True, index=True)
    partner_id = Column(GUID(), ForeignKey("partners.id", ondelete="RESTRICT"), nullable=True, index=True)
    service_type = Column(ExistingEnum(VehicleServiceType, name="vehicle_service_type"), nullable=True)
    service_at_km = Column(Numeric(18, 4), nullable=True)
    service_at = Column(DateTime(timezone=True), nullable=True)

    proof_id = Column(GUID(), ForeignKey("service_completion_proofs.id", ondelete="RESTRICT"), nullable=True, index=True)
    work_summary = Column(Text, nullable=True)
    odometer_km = Column(Numeric(18, 4), nullable=True)
    performed_at = Column(DateTime(timezone=True), nullable=True)
    verified = Column(Boolean, nullable=True, default=True)

    item_code = Column(String(64), ForeignKey("maintenance_items.code"), nullable=True)
    order_id = Column(GUID(), nullable=True)
    note = Column(Text, nullable=True)
    source = Column(String(32), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["VehicleServiceRecord"]
