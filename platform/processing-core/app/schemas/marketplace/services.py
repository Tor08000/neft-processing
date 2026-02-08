from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.marketplace_catalog import MarketplaceServiceStatus


ROLE_ADMIN = "admin"
ROLE_PARTNER = "partner"

ALLOWED_TRANSITIONS: dict[MarketplaceServiceStatus, dict[MarketplaceServiceStatus, set[str]]] = {
    MarketplaceServiceStatus.DRAFT: {
        MarketplaceServiceStatus.PENDING_REVIEW: {ROLE_PARTNER, ROLE_ADMIN},
        MarketplaceServiceStatus.ARCHIVED: {ROLE_PARTNER, ROLE_ADMIN},
    },
    MarketplaceServiceStatus.PENDING_REVIEW: {
        MarketplaceServiceStatus.ACTIVE: {ROLE_ADMIN},
        MarketplaceServiceStatus.DRAFT: {ROLE_ADMIN},
        MarketplaceServiceStatus.ARCHIVED: {ROLE_PARTNER, ROLE_ADMIN},
    },
    MarketplaceServiceStatus.ACTIVE: {
        MarketplaceServiceStatus.SUSPENDED: {ROLE_ADMIN},
    },
    MarketplaceServiceStatus.SUSPENDED: {
        MarketplaceServiceStatus.ACTIVE: {ROLE_ADMIN},
        MarketplaceServiceStatus.ARCHIVED: {ROLE_PARTNER, ROLE_ADMIN},
    },
    MarketplaceServiceStatus.ARCHIVED: {},
}


def assert_transition(
    old_status: MarketplaceServiceStatus,
    new_status: MarketplaceServiceStatus,
    *,
    actor_role: str | None = None,
) -> None:
    if old_status == new_status:
        return
    allowed = ALLOWED_TRANSITIONS.get(old_status, {}).get(new_status)
    if not allowed:
        raise ValueError("SERVICE_STATE_INVALID")
    if actor_role and actor_role not in allowed:
        raise ValueError("SERVICE_STATE_INVALID")


def assert_editable(status: MarketplaceServiceStatus) -> None:
    if status != MarketplaceServiceStatus.DRAFT:
        raise ValueError("INVALID_STATE")


class ServiceMediaCreate(BaseModel):
    attachment_id: str
    bucket: str
    path: str
    checksum: str | None = None
    size: int | None = None
    mime: str | None = None
    sort_index: int | None = None


class ServiceMediaOut(ServiceMediaCreate):
    created_at: datetime | None = None


class ServiceCardBase(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default="", max_length=5000)
    category: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    duration_min: int = Field(ge=5, le=1440)
    requirements: str | None = Field(default=None)

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("tags_invalid")

    @model_validator(mode="after")
    def _validate_lengths(self) -> "ServiceCardBase":
        if self.description and len(self.description) > 5000:
            raise ValueError("description_too_long")
        return self


class ServiceCardCreate(ServiceCardBase):
    pass


class ServiceCardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = None
    tags: list[str] | None = None
    attributes: dict[str, Any] | None = None
    duration_min: int | None = Field(default=None, ge=5, le=1440)
    requirements: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("tags_invalid")


class ServiceCardOut(ServiceCardBase):
    id: str
    partner_id: str
    status: str
    media: list[ServiceMediaOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None


class ServiceCardListOut(BaseModel):
    id: str
    partner_id: str
    title: str
    category: str
    status: str
    duration_min: int
    updated_at: datetime | None = None
    created_at: datetime | None = None


class ServiceCardListResponse(BaseModel):
    items: list[ServiceCardListOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class ServiceLocationCreate(BaseModel):
    location_id: str
    is_active: bool = True
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ServiceLocationOut(BaseModel):
    id: str
    service_id: str
    location_id: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool
    created_at: datetime | None = None


class ServiceScheduleRuleCreate(BaseModel):
    weekday: int = Field(ge=0, le=6)
    time_from: str
    time_to: str
    slot_duration_min: int | None = Field(default=None, ge=5, le=1440)
    capacity: int = Field(ge=1)


class ServiceScheduleRuleOut(ServiceScheduleRuleCreate):
    id: str
    service_location_id: str
    slot_duration_min: int
    created_at: datetime | None = None


class ServiceScheduleExceptionCreate(BaseModel):
    date: date
    is_closed: bool = False
    time_from: str | None = None
    time_to: str | None = None
    capacity_override: int | None = Field(default=None, ge=1)


class ServiceScheduleExceptionOut(ServiceScheduleExceptionCreate):
    id: str
    service_location_id: str
    created_at: datetime | None = None


class ServiceScheduleOut(BaseModel):
    rules: list[ServiceScheduleRuleOut] = Field(default_factory=list)
    exceptions: list[ServiceScheduleExceptionOut] = Field(default_factory=list)


class ServiceAvailabilitySlot(BaseModel):
    service_location_id: str
    location_id: str
    date: date
    time_from: str
    time_to: str
    capacity: int


class ServiceAvailabilityResponse(BaseModel):
    items: list[ServiceAvailabilitySlot] = Field(default_factory=list)
