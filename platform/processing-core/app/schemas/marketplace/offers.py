from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.marketplace_offers import (
    MarketplaceOfferEntitlementScope,
    MarketplaceOfferGeoScope,
    MarketplaceOfferPriceModel,
    MarketplaceOfferStatus,
    MarketplaceOfferSubjectType,
)

ROLE_ADMIN = "admin"
ROLE_PARTNER = "partner"

ALLOWED_TRANSITIONS: dict[MarketplaceOfferStatus, dict[MarketplaceOfferStatus, set[str]]] = {
    MarketplaceOfferStatus.DRAFT: {
        MarketplaceOfferStatus.PENDING_REVIEW: {ROLE_PARTNER, ROLE_ADMIN},
        MarketplaceOfferStatus.ARCHIVED: {ROLE_PARTNER, ROLE_ADMIN},
    },
    MarketplaceOfferStatus.PENDING_REVIEW: {
        MarketplaceOfferStatus.ACTIVE: {ROLE_ADMIN},
        MarketplaceOfferStatus.DRAFT: {ROLE_ADMIN},
    },
    MarketplaceOfferStatus.ACTIVE: {
        MarketplaceOfferStatus.SUSPENDED: {ROLE_ADMIN},
    },
    MarketplaceOfferStatus.SUSPENDED: {
        MarketplaceOfferStatus.ACTIVE: {ROLE_ADMIN},
    },
    MarketplaceOfferStatus.ARCHIVED: {},
}

_TIME_WINDOW_RE = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")


def assert_transition(
    old_status: MarketplaceOfferStatus,
    new_status: MarketplaceOfferStatus,
    *,
    actor_role: str | None = None,
) -> None:
    if old_status == new_status:
        return
    allowed = ALLOWED_TRANSITIONS.get(old_status, {}).get(new_status)
    if not allowed:
        raise ValueError("OFFER_STATE_INVALID")
    if actor_role and actor_role not in allowed:
        raise ValueError("OFFER_STATE_INVALID")


def assert_editable(status: MarketplaceOfferStatus) -> None:
    if status != MarketplaceOfferStatus.DRAFT:
        raise ValueError("INVALID_STATE")


def _validate_time_windows(value: list[str]) -> list[str]:
    for item in value:
        match = _TIME_WINDOW_RE.match(item)
        if not match:
            raise ValueError("time_window_invalid")
        start_h, start_m, end_h, end_m = map(int, match.groups())
        start = start_h * 60 + start_m
        end = end_h * 60 + end_m
        if start < 0 or end < 0 or start >= 24 * 60 or end > 24 * 60 or start >= end:
            raise ValueError("time_window_invalid")
    return value


class OfferTerms(BaseModel):
    min_qty: int | None = Field(default=None, ge=0)
    max_qty: int | None = Field(default=None, ge=0)
    min_amount: float | None = Field(default=None, ge=0)
    max_amount: float | None = Field(default=None, ge=0)
    lead_time_minutes: int | None = Field(default=None, ge=0)
    cancellation_policy: str | None = None
    allowed_weekdays: list[int] | None = None
    time_windows: list[str] | None = None

    @field_validator("allowed_weekdays")
    @classmethod
    def _validate_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if not all(0 <= item <= 6 for item in value):
            raise ValueError("weekday_invalid")
        return value

    @field_validator("time_windows")
    @classmethod
    def _validate_windows(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        return _validate_time_windows(value)

    @model_validator(mode="after")
    def _validate_ranges(self) -> "OfferTerms":
        if self.min_qty is not None and self.max_qty is not None and self.min_qty > self.max_qty:
            raise ValueError("min_qty_gt_max_qty")
        if self.min_amount is not None and self.max_amount is not None and self.min_amount > self.max_amount:
            raise ValueError("min_amount_gt_max_amount")
        return self


class OfferBase(BaseModel):
    subject_type: MarketplaceOfferSubjectType
    subject_id: str
    title_override: str | None = None
    description_override: str | None = None
    currency: str = Field(min_length=1)
    price_model: MarketplaceOfferPriceModel
    price_amount: float | None = Field(default=None, ge=0)
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    vat_rate: float | None = Field(default=None, ge=0)
    terms: OfferTerms = Field(default_factory=OfferTerms)
    geo_scope: MarketplaceOfferGeoScope
    location_ids: list[str] | None = None
    region_code: str | None = None
    entitlement_scope: MarketplaceOfferEntitlementScope
    allowed_subscription_codes: list[str] | None = None
    allowed_client_ids: list[str] | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def _validate_price_model(self) -> "OfferBase":
        if self.price_model in {
            MarketplaceOfferPriceModel.FIXED,
            MarketplaceOfferPriceModel.PER_UNIT,
            MarketplaceOfferPriceModel.PER_SERVICE,
        }:
            if self.price_amount is None:
                raise ValueError("price_amount_required")
        if self.price_model == MarketplaceOfferPriceModel.RANGE:
            if self.price_min is None or self.price_max is None:
                raise ValueError("price_range_required")
            if self.price_min > self.price_max:
                raise ValueError("price_range_invalid")
        return self

    @model_validator(mode="after")
    def _validate_geo_scope(self) -> "OfferBase":
        if self.geo_scope == MarketplaceOfferGeoScope.SELECTED_LOCATIONS:
            if not self.location_ids:
                raise ValueError("location_ids_required")
        if self.geo_scope == MarketplaceOfferGeoScope.REGION:
            if not self.region_code:
                raise ValueError("region_code_required")
        return self

    @model_validator(mode="after")
    def _validate_entitlements(self) -> "OfferBase":
        if self.entitlement_scope == MarketplaceOfferEntitlementScope.SUBSCRIPTION_ONLY:
            if not self.allowed_subscription_codes:
                raise ValueError("subscription_codes_required")
        if self.entitlement_scope == MarketplaceOfferEntitlementScope.SEGMENT_ONLY:
            if not self.allowed_client_ids:
                raise ValueError("client_ids_required")
        return self

    @model_validator(mode="after")
    def _validate_validity(self) -> "OfferBase":
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("validity_invalid")
        return self


class OfferCreate(OfferBase):
    pass


class OfferUpdate(BaseModel):
    title_override: str | None = None
    description_override: str | None = None
    currency: str | None = Field(default=None, min_length=1)
    price_model: MarketplaceOfferPriceModel | None = None
    price_amount: float | None = Field(default=None, ge=0)
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    vat_rate: float | None = Field(default=None, ge=0)
    terms: OfferTerms | None = None
    geo_scope: MarketplaceOfferGeoScope | None = None
    location_ids: list[str] | None = None
    region_code: str | None = None
    entitlement_scope: MarketplaceOfferEntitlementScope | None = None
    allowed_subscription_codes: list[str] | None = None
    allowed_client_ids: list[str] | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def _validate_validity(self) -> "OfferUpdate":
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("validity_invalid")
        return self


class OfferOut(BaseModel):
    id: str
    partner_id: str
    subject_type: str
    subject_id: str
    title_override: str | None
    description_override: str | None
    status: str
    moderation_comment: str | None
    currency: str
    price_model: str
    price_amount: float | None
    price_min: float | None
    price_max: float | None
    vat_rate: float | None
    terms: dict[str, Any]
    geo_scope: str
    location_ids: list[str]
    region_code: str | None
    entitlement_scope: str
    allowed_subscription_codes: list[str]
    allowed_client_ids: list[str]
    valid_from: datetime | None
    valid_to: datetime | None
    created_at: datetime
    updated_at: datetime | None = None


class OfferListOut(BaseModel):
    id: str
    partner_id: str
    subject_type: str
    subject_id: str
    title_override: str | None
    status: str
    price_model: str
    currency: str
    geo_scope: str
    entitlement_scope: str
    valid_from: datetime | None
    valid_to: datetime | None


class OfferListResponse(BaseModel):
    items: list[OfferListOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class OfferModerationRejectRequest(BaseModel):
    reason_code: str
    comment: str = Field(min_length=10, max_length=2000)
