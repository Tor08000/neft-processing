from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, Text, event, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")
RESOURCE_ID_ARRAY = postgresql.ARRAY(GUID()).with_variant(JSON(), "sqlite")


class PartnerServiceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


class PartnerResourceType(str, Enum):
    BAY = "BAY"
    TECHNICIAN = "TECHNICIAN"


class PartnerResourceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ServiceBookingStatus(str, Enum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    DECLINED = "DECLINED"
    CANCELED = "CANCELED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class BookingPaymentStatus(str, Enum):
    NONE = "NONE"
    AUTHORIZED = "AUTHORIZED"
    PAID = "PAID"
    REFUNDED = "REFUNDED"


class ServiceBookingEventType(str, Enum):
    CREATED = "CREATED"
    SLOT_LOCKED = "SLOT_LOCKED"
    CONFIRMED = "CONFIRMED"
    DECLINED = "DECLINED"
    CANCELED = "CANCELED"
    RESCHEDULED = "RESCHEDULED"
    PAID = "PAID"
    REFUNDED = "REFUNDED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class ServiceBookingActorType(str, Enum):
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"
    SYSTEM = "SYSTEM"
    ADMIN = "ADMIN"


class ServiceBookingImmutableError(ValueError):
    """Raised when WORM-protected booking records are mutated."""


class PartnerService(ServiceBookingBase):
    __tablename__ = "partner_services"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    category_code = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    base_price = Column(Numeric(18, 4), nullable=False)
    currency = Column(Text, nullable=False, default="RUB")
    requires_vehicle = Column(Boolean, nullable=False, default=True)
    requires_odometer = Column(Boolean, nullable=False, default=False)
    status = Column(
        ExistingEnum(PartnerServiceStatus, name="partner_service_status"),
        nullable=False,
        default=PartnerServiceStatus.ACTIVE.value,
    )
    meta = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class PartnerServiceCalendar(ServiceBookingBase):
    __tablename__ = "partner_service_calendars"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    location_id = Column(GUID(), nullable=True, index=True)
    timezone = Column(Text, nullable=False)
    working_hours = Column(JSON_TYPE, nullable=False)
    holidays = Column(JSON_TYPE, nullable=True)
    slot_step_minutes = Column(Integer, nullable=False, default=30)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class PartnerResource(ServiceBookingBase):
    __tablename__ = "partner_resources"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    title = Column(Text, nullable=False)
    resource_type = Column(
        ExistingEnum(PartnerResourceType, name="partner_resource_type"),
        nullable=False,
    )
    capacity = Column(Integer, nullable=False, default=1)
    status = Column(
        ExistingEnum(PartnerResourceStatus, name="partner_resource_status"),
        nullable=False,
        default=PartnerResourceStatus.ACTIVE.value,
    )
    meta = Column(JSON_TYPE, nullable=True)


class ServiceAvailabilityRule(ServiceBookingBase):
    __tablename__ = "service_availability_rules"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    service_id = Column(GUID(), ForeignKey("partner_services.id", ondelete="RESTRICT"), nullable=False, index=True)
    resource_ids = Column(RESOURCE_ID_ARRAY, nullable=True)
    lead_time_minutes = Column(Integer, nullable=False, default=60)
    max_days_ahead = Column(Integer, nullable=False, default=14)
    parallel_capacity = Column(Integer, nullable=False, default=1)
    meta = Column(JSON_TYPE, nullable=True)


class BookingSlotLock(ServiceBookingBase):
    __tablename__ = "booking_slot_locks"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    service_id = Column(GUID(), ForeignKey("partner_services.id", ondelete="RESTRICT"), nullable=False, index=True)
    resource_id = Column(GUID(), ForeignKey("partner_resources.id", ondelete="RESTRICT"), nullable=True, index=True)
    starts_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    client_id = Column(GUID(), nullable=False, index=True)
    booking_id = Column(GUID(), ForeignKey("service_bookings.id", ondelete="SET NULL"), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ServiceBooking(ServiceBookingBase):
    __tablename__ = "service_bookings"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    booking_number = Column(Text, nullable=False, unique=True)
    client_id = Column(GUID(), nullable=False, index=True)
    user_id = Column(GUID(), nullable=True, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    service_id = Column(GUID(), ForeignKey("partner_services.id", ondelete="RESTRICT"), nullable=False, index=True)
    vehicle_id = Column(GUID(), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True)
    odometer_km = Column(Numeric(18, 4), nullable=True)
    recommendation_id = Column(GUID(), ForeignKey("vehicle_recommendations.id", ondelete="SET NULL"), nullable=True)
    status = Column(
        ExistingEnum(ServiceBookingStatus, name="service_booking_status"),
        nullable=False,
        default=ServiceBookingStatus.REQUESTED.value,
    )
    starts_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    resource_id = Column(GUID(), ForeignKey("partner_resources.id", ondelete="RESTRICT"), nullable=True, index=True)
    price_snapshot_json = Column(JSON_TYPE, nullable=False)
    promo_applied_json = Column(JSON_TYPE, nullable=True)
    payment_status = Column(
        ExistingEnum(BookingPaymentStatus, name="booking_payment_status"),
        nullable=False,
        default=BookingPaymentStatus.NONE.value,
    )
    client_note = Column(Text, nullable=True)
    partner_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class ServiceBookingEvent(ServiceBookingBase):
    __tablename__ = "service_booking_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    booking_id = Column(GUID(), ForeignKey("service_bookings.id", ondelete="RESTRICT"), nullable=False, index=True)
    event_type = Column(
        ExistingEnum(ServiceBookingEventType, name="service_booking_event_type"),
        nullable=False,
    )
    actor_type = Column(
        ExistingEnum(ServiceBookingActorType, name="service_booking_actor_type"),
        nullable=False,
    )
    actor_id = Column(GUID(), nullable=True)
    payload = Column(JSON_TYPE, nullable=False)
    audit_event_id = Column(GUID(), ForeignKey("case_events.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


@event.listens_for(ServiceBookingEvent, "before_update")
@event.listens_for(ServiceBookingEvent, "before_delete")
def _block_service_booking_event_mutation(mapper, connection, target: ServiceBookingEvent) -> None:
    raise ServiceBookingImmutableError("service_booking_event_immutable")


__all__ = [
    "BookingPaymentStatus",
    "BookingSlotLock",
    "PartnerResource",
    "PartnerResourceStatus",
    "PartnerResourceType",
    "PartnerService",
    "PartnerServiceCalendar",
    "PartnerServiceStatus",
    "ServiceAvailabilityRule",
    "ServiceBooking",
    "ServiceBookingActorType",
    "ServiceBookingEvent",
    "ServiceBookingEventType",
    "ServiceBookingImmutableError",
    "ServiceBookingStatus",
]
