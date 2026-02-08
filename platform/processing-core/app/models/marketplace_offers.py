from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Numeric, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str

JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class MarketplaceOfferSubjectType(str, Enum):
    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"


class MarketplaceOfferStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class MarketplaceOfferPriceModel(str, Enum):
    FIXED = "FIXED"
    RANGE = "RANGE"
    PER_UNIT = "PER_UNIT"
    PER_SERVICE = "PER_SERVICE"


class MarketplaceOfferGeoScope(str, Enum):
    ALL_PARTNER_LOCATIONS = "ALL_PARTNER_LOCATIONS"
    SELECTED_LOCATIONS = "SELECTED_LOCATIONS"
    REGION = "REGION"


class MarketplaceOfferEntitlementScope(str, Enum):
    ALL_CLIENTS = "ALL_CLIENTS"
    SUBSCRIPTION_ONLY = "SUBSCRIPTION_ONLY"
    SEGMENT_ONLY = "SEGMENT_ONLY"


class MarketplaceOffer(Base):
    __tablename__ = "marketplace_offers"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_id = Column(GUID(), nullable=False, index=True)
    subject_type = Column(
        ExistingEnum(MarketplaceOfferSubjectType, name="marketplace_offer_subject_type"),
        nullable=False,
    )
    subject_id = Column(GUID(), nullable=False, index=True)
    title_override = Column(Text, nullable=True)
    description_override = Column(Text, nullable=True)
    status = Column(
        ExistingEnum(MarketplaceOfferStatus, name="marketplace_offer_status"),
        nullable=False,
        default=MarketplaceOfferStatus.DRAFT.value,
    )
    moderation_comment = Column(Text, nullable=True)
    currency = Column(Text, nullable=False)
    price_model = Column(
        ExistingEnum(MarketplaceOfferPriceModel, name="marketplace_offer_price_model"),
        nullable=False,
    )
    price_amount = Column(Numeric(12, 2), nullable=True)
    price_min = Column(Numeric(12, 2), nullable=True)
    price_max = Column(Numeric(12, 2), nullable=True)
    vat_rate = Column(Numeric(5, 2), nullable=True)
    terms = Column(JSON_TYPE, nullable=False, default=dict)
    geo_scope = Column(
        ExistingEnum(MarketplaceOfferGeoScope, name="marketplace_offer_geo_scope"),
        nullable=False,
    )
    location_ids = Column(JSON_TYPE, nullable=False, default=list)
    region_code = Column(Text, nullable=True)
    entitlement_scope = Column(
        ExistingEnum(MarketplaceOfferEntitlementScope, name="marketplace_offer_entitlement_scope"),
        nullable=False,
    )
    allowed_subscription_codes = Column(JSON_TYPE, nullable=False, default=list)
    allowed_client_ids = Column(JSON_TYPE, nullable=False, default=list)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
