from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Integer, Numeric, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class MarketplaceCommissionScope(str, Enum):
    MARKETPLACE = "MARKETPLACE"


class MarketplaceCommissionType(str, Enum):
    PERCENT = "PERCENT"
    FIXED = "FIXED"
    TIERED = "TIERED"


class MarketplaceCommissionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class MarketplaceCommissionRule(Base):
    __tablename__ = "marketplace_commission_rules"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    scope = Column(
        ExistingEnum(MarketplaceCommissionScope, name="marketplace_commission_scope"),
        nullable=False,
        default=MarketplaceCommissionScope.MARKETPLACE.value,
    )
    partner_id = Column(GUID(), nullable=True, index=True)
    product_category = Column(Text, nullable=True, index=True)
    commission_type = Column(
        ExistingEnum(MarketplaceCommissionType, name="marketplace_commission_type"),
        nullable=False,
    )
    rate = Column(Numeric(12, 6), nullable=True)
    amount = Column(Numeric(18, 4), nullable=True)
    tiers = Column(JSON_TYPE, nullable=True)
    min_commission = Column(Numeric(18, 4), nullable=True)
    max_commission = Column(Numeric(18, 4), nullable=True)
    effective_from = Column(DateTime(timezone=True), nullable=True, index=True)
    effective_to = Column(DateTime(timezone=True), nullable=True, index=True)
    priority = Column(Integer, nullable=False, default=100, index=True)
    status = Column(
        ExistingEnum(MarketplaceCommissionStatus, name="marketplace_commission_status"),
        nullable=False,
        default=MarketplaceCommissionStatus.ACTIVE.value,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = [
    "MarketplaceCommissionRule",
    "MarketplaceCommissionScope",
    "MarketplaceCommissionStatus",
    "MarketplaceCommissionType",
]
