from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, root_validator


ProductType = Literal["SERVICE", "PRODUCT"]
PriceModel = Literal["FIXED", "PER_UNIT", "TIERED"]
ProductStatus = Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
ModerationStatus = Literal["DRAFT", "PENDING_REVIEW", "APPROVED", "REJECTED"]
VerificationStatus = Literal["PENDING", "VERIFIED", "REJECTED"]


def _require_numeric(value: Any, field_name: str) -> None:
    if not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{field_name}_must_be_numeric")


def validate_price_config(price_model: str | None, price_config: dict | None) -> None:
    if price_model is None or price_config is None:
        return

    if price_model == "FIXED":
        if not {"amount", "currency"}.issubset(price_config):
            raise ValueError("price_config_missing_fields")
        _require_numeric(price_config.get("amount"), "amount")
        if price_config.get("currency") != "RUB":
            raise ValueError("currency_not_supported")
        return

    if price_model == "PER_UNIT":
        if not {"unit", "amount_per_unit", "currency"}.issubset(price_config):
            raise ValueError("price_config_missing_fields")
        if price_config.get("unit") not in {"liter", "item", "hour"}:
            raise ValueError("unit_not_supported")
        _require_numeric(price_config.get("amount_per_unit"), "amount_per_unit")
        if price_config.get("currency") != "RUB":
            raise ValueError("currency_not_supported")
        return

    if price_model == "TIERED":
        if not {"currency", "tiers"}.issubset(price_config):
            raise ValueError("price_config_missing_fields")
        if price_config.get("currency") != "RUB":
            raise ValueError("currency_not_supported")
        tiers = price_config.get("tiers")
        if not isinstance(tiers, list) or not tiers:
            raise ValueError("tiers_required")
        for tier in tiers:
            if not isinstance(tier, dict):
                raise ValueError("tier_invalid")
            if "from" not in tier or "amount" not in tier:
                raise ValueError("tier_missing_fields")
            _require_numeric(tier.get("from"), "from")
            if tier.get("to") is not None:
                _require_numeric(tier.get("to"), "to")
            _require_numeric(tier.get("amount"), "amount")
        return

    raise ValueError("price_model_not_supported")


class PartnerProfileCreate(BaseModel):
    company_name: str
    description: str | None = None


class PartnerProfileUpdate(BaseModel):
    company_name: str | None = None
    description: str | None = None


class PartnerProfileOut(BaseModel):
    id: str
    partner_id: str
    company_name: str
    description: str | None = None
    verification_status: VerificationStatus
    rating: Decimal | None = None
    created_at: datetime
    updated_at: datetime | None = None
    audit_event_id: str | None = None


class PartnerProfileListResponse(BaseModel):
    items: list[PartnerProfileOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class PartnerVerifyRequest(BaseModel):
    status: VerificationStatus = "VERIFIED"
    reason: str | None = None


class ProductCreate(BaseModel):
    type: ProductType
    title: str
    description: str
    category: str
    price_model: PriceModel
    price_config: dict

    @root_validator(skip_on_failure=True)
    def _check_price_config(cls, values: dict) -> dict:
        validate_price_config(values.get("price_model"), values.get("price_config"))
        return values


class ProductUpdate(BaseModel):
    type: ProductType | None = None
    title: str | None = None
    description: str | None = None
    category: str | None = None
    price_model: PriceModel | None = None
    price_config: dict | None = None

    @root_validator(skip_on_failure=True)
    def _check_price_config(cls, values: dict) -> dict:
        price_model = values.get("price_model")
        price_config = values.get("price_config")
        if price_model and price_config is not None:
            validate_price_config(price_model, price_config)
        return values


class ProductOut(BaseModel):
    id: str
    partner_id: str
    type: ProductType
    title: str
    description: str
    category: str
    price_model: PriceModel
    price_config: dict
    status: ProductStatus
    moderation_status: ModerationStatus
    moderation_reason: str | None = None
    moderated_by: str | None = None
    moderated_at: datetime | None = None
    published_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    audit_event_id: str | None = None


class ProductListOut(BaseModel):
    id: str
    partner_id: str
    type: ProductType
    title: str
    category: str
    price_model: PriceModel
    price_config: dict
    status: ProductStatus
    moderation_status: ModerationStatus
    updated_at: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime | None = None
    sponsored: bool = False
    sponsored_badge: str | None = None
    sponsored_campaign_id: str | None = None


class ProductListResponse(BaseModel):
    items: list[ProductListOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class ProductStatusUpdateRequest(BaseModel):
    status: ProductStatus
    reason: str | None = None


class ProductModerationRejectRequest(BaseModel):
    reason: str
