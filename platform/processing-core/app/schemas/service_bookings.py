from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


PartnerServiceStatus = Literal["ACTIVE", "PAUSED"]
PartnerResourceType = Literal["BAY", "TECHNICIAN"]
PartnerResourceStatus = Literal["ACTIVE", "INACTIVE"]
BookingStatus = Literal[
    "REQUESTED",
    "CONFIRMED",
    "DECLINED",
    "CANCELED",
    "IN_PROGRESS",
    "COMPLETED",
    "NO_SHOW",
]
BookingPaymentStatus = Literal["NONE", "AUTHORIZED", "PAID", "REFUNDED"]
BookingEventType = Literal[
    "CREATED",
    "SLOT_LOCKED",
    "CONFIRMED",
    "DECLINED",
    "CANCELED",
    "RESCHEDULED",
    "PAID",
    "REFUNDED",
    "STARTED",
    "COMPLETED",
    "NO_SHOW",
]
BookingActorType = Literal["CLIENT", "PARTNER", "SYSTEM", "ADMIN"]


class PartnerServiceOut(BaseModel):
    id: str
    partner_id: str
    title: str
    description: str | None = None
    category_code: str | None = None
    duration_minutes: int
    base_price: Decimal
    currency: str
    requires_vehicle: bool
    requires_odometer: bool
    status: PartnerServiceStatus
    meta: dict | None = None
    created_at: datetime
    updated_at: datetime | None = None


class PartnerResourceIn(BaseModel):
    title: str
    resource_type: PartnerResourceType
    capacity: int = Field(default=1, ge=1)
    status: PartnerResourceStatus = "ACTIVE"
    meta: dict | None = None


class PartnerResourceOut(PartnerResourceIn):
    id: str
    partner_id: str


class PartnerCalendarIn(BaseModel):
    timezone: str
    working_hours: dict[str, list[dict[str, str]]]
    holidays: dict | None = None
    slot_step_minutes: int = Field(default=30, ge=5, le=240)


class PartnerCalendarOut(PartnerCalendarIn):
    id: str
    partner_id: str
    location_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AvailabilityRuleIn(BaseModel):
    service_id: str
    resource_ids: list[str] | None = None
    lead_time_minutes: int = Field(default=60, ge=0)
    max_days_ahead: int = Field(default=14, ge=1, le=90)
    parallel_capacity: int = Field(default=1, ge=1)
    meta: dict | None = None


class AvailabilityRuleOut(AvailabilityRuleIn):
    id: str
    partner_id: str


class SlotOut(BaseModel):
    start: datetime
    end: datetime
    resource_id: str | None = None


class SlotListOut(BaseModel):
    timezone: str
    slot_step: int
    items: list[SlotOut]


class SlotLockRequest(BaseModel):
    partner_id: str
    service_id: str
    resource_id: str | None = None
    start: datetime
    end: datetime
    vehicle_id: str | None = None


class SlotLockOut(BaseModel):
    lock_id: str
    expires_at: datetime


class QuoteRequest(BaseModel):
    service_id: str
    vehicle_id: str | None = None
    coupon_code: str | None = None


class QuoteResponse(BaseModel):
    price_snapshot: dict[str, Any]


class BookingCreateRequest(BaseModel):
    lock_id: str
    vehicle_id: str | None = None
    recommendation_id: str | None = None
    client_note: str | None = None


class BookingCancelRequest(BaseModel):
    reason: str | None = None


class BookingEventOut(BaseModel):
    id: str
    booking_id: str
    event_type: BookingEventType
    actor_type: BookingActorType
    actor_id: str | None = None
    payload: dict
    audit_event_id: str
    created_at: datetime


class BookingOut(BaseModel):
    id: str
    booking_number: str
    client_id: str
    partner_id: str
    service_id: str
    vehicle_id: str | None = None
    odometer_km: Decimal | None = None
    recommendation_id: str | None = None
    status: BookingStatus
    starts_at: datetime
    ends_at: datetime
    resource_id: str | None = None
    price_snapshot_json: dict
    promo_applied_json: dict | None = None
    payment_status: BookingPaymentStatus
    client_note: str | None = None
    partner_note: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class BookingDetailOut(BookingOut):
    events: list[BookingEventOut] = Field(default_factory=list)
