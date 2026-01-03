from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Numeric, Text, event, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class PartnerVerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class MarketplaceProductType(str, Enum):
    SERVICE = "SERVICE"
    PRODUCT = "PRODUCT"


class MarketplacePriceModel(str, Enum):
    FIXED = "FIXED"
    PER_UNIT = "PER_UNIT"
    TIERED = "TIERED"


class MarketplaceProductStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class MarketplaceProductModerationStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MarketplaceCatalogImmutableError(ValueError):
    """Raised when WORM-protected marketplace records are mutated."""


class PartnerProfile(Base):
    __tablename__ = "partner_profiles"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_id = Column(GUID(), nullable=False, unique=True, index=True)
    company_name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    verification_status = Column(
        ExistingEnum(PartnerVerificationStatus, name="partner_verification_status"),
        nullable=False,
        default=PartnerVerificationStatus.PENDING.value,
    )
    rating = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    audit_event_id = Column(GUID(), nullable=True)


class MarketplaceProduct(Base):
    __tablename__ = "marketplace_products"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_id = Column(GUID(), nullable=False, index=True)
    type = Column(ExistingEnum(MarketplaceProductType, name="marketplace_product_type"), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    price_model = Column(ExistingEnum(MarketplacePriceModel, name="marketplace_price_model"), nullable=False)
    price_config = Column(JSON_TYPE, nullable=False)
    status = Column(
        ExistingEnum(MarketplaceProductStatus, name="marketplace_product_status"),
        nullable=False,
        default=MarketplaceProductStatus.DRAFT.value,
    )
    moderation_status = Column(
        ExistingEnum(MarketplaceProductModerationStatus, name="marketplace_product_moderation_status"),
        nullable=False,
        default=MarketplaceProductModerationStatus.DRAFT.value,
    )
    moderation_reason = Column(Text, nullable=True)
    moderated_by = Column(GUID(), nullable=True)
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    audit_event_id = Column(GUID(), nullable=True)


@event.listens_for(PartnerProfile, "before_delete")
@event.listens_for(MarketplaceProduct, "before_delete")
def _block_marketplace_delete(mapper, connection, target) -> None:
    raise MarketplaceCatalogImmutableError("marketplace_catalog_worm")


__all__ = [
    "MarketplaceCatalogImmutableError",
    "MarketplacePriceModel",
    "MarketplaceProduct",
    "MarketplaceProductModerationStatus",
    "MarketplaceProductStatus",
    "MarketplaceProductType",
    "PartnerProfile",
    "PartnerVerificationStatus",
]
