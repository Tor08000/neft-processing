from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.marketplace_catalog import MarketplaceProductCardStatus


ROLE_ADMIN = "admin"
ROLE_PARTNER = "partner"

ALLOWED_TRANSITIONS: dict[MarketplaceProductCardStatus, dict[MarketplaceProductCardStatus, set[str]]] = {
    MarketplaceProductCardStatus.DRAFT: {
        MarketplaceProductCardStatus.PENDING_REVIEW: {ROLE_PARTNER, ROLE_ADMIN},
        MarketplaceProductCardStatus.ARCHIVED: {ROLE_PARTNER, ROLE_ADMIN},
    },
    MarketplaceProductCardStatus.PENDING_REVIEW: {
        MarketplaceProductCardStatus.ACTIVE: {ROLE_ADMIN},
        MarketplaceProductCardStatus.ARCHIVED: {ROLE_PARTNER, ROLE_ADMIN},
    },
    MarketplaceProductCardStatus.ACTIVE: {
        MarketplaceProductCardStatus.SUSPENDED: {ROLE_ADMIN},
    },
    MarketplaceProductCardStatus.SUSPENDED: {
        MarketplaceProductCardStatus.ACTIVE: {ROLE_ADMIN},
        MarketplaceProductCardStatus.ARCHIVED: {ROLE_PARTNER, ROLE_ADMIN},
    },
    MarketplaceProductCardStatus.ARCHIVED: {},
}


def assert_transition(
    old_status: MarketplaceProductCardStatus,
    new_status: MarketplaceProductCardStatus,
    *,
    actor_role: str | None = None,
) -> None:
    if old_status == new_status:
        return
    allowed = ALLOWED_TRANSITIONS.get(old_status, {}).get(new_status)
    if not allowed:
        raise ValueError("PRODUCT_CARD_STATE_INVALID")
    if actor_role and actor_role not in allowed:
        raise ValueError("PRODUCT_CARD_STATE_INVALID")


def assert_editable(status: MarketplaceProductCardStatus) -> None:
    if status != MarketplaceProductCardStatus.DRAFT:
        raise ValueError("INVALID_STATE")


class ProductMediaCreate(BaseModel):
    attachment_id: str
    bucket: str
    path: str
    checksum: str | None = None
    size: int | None = None
    mime: str | None = None
    sort_index: int | None = None


class ProductMediaOut(ProductMediaCreate):
    created_at: datetime | None = None


class ProductCardBase(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default="", max_length=5000)
    category: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    variants: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("tags_invalid")

    @model_validator(mode="after")
    def _validate_lengths(self) -> "ProductCardBase":
        if self.description and len(self.description) > 5000:
            raise ValueError("description_too_long")
        return self


class ProductCardCreate(ProductCardBase):
    pass


class ProductCardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = None
    tags: list[str] | None = None
    attributes: dict[str, Any] | None = None
    variants: list[dict[str, Any]] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("tags_invalid")


class ProductCardOut(ProductCardBase):
    id: str
    partner_id: str
    status: str
    media: list[ProductMediaOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None


class ProductCardListOut(BaseModel):
    id: str
    partner_id: str
    title: str
    category: str
    status: str
    updated_at: datetime | None = None
    created_at: datetime | None = None


class ProductCardListResponse(BaseModel):
    items: list[ProductCardListOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
