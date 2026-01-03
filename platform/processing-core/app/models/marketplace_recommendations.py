from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Integer, Numeric, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import PrimaryKeyConstraint
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class MarketplaceEventType(str, Enum):
    VIEW = "VIEW"
    CLICK = "CLICK"
    ADD_TO_CART = "ADD_TO_CART"
    PURCHASE = "PURCHASE"
    REFUND = "REFUND"


class MarketplaceEvent(Base):
    __tablename__ = "marketplace_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=True, index=True)
    client_id = Column(GUID(), nullable=False, index=True)
    user_id = Column(GUID(), nullable=True)
    partner_id = Column(GUID(), nullable=True, index=True)
    product_id = Column(GUID(), nullable=True, index=True)
    event_type = Column(ExistingEnum(MarketplaceEventType, name="marketplace_event_type"), nullable=False)
    event_ts = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    context = Column(JSON_TYPE, nullable=True)
    meta = Column(JSON_TYPE, nullable=True)


class ClientBehaviorProfile(Base):
    __tablename__ = "client_behavior_profiles"

    tenant_id = Column(GUID(), nullable=True, index=True)
    client_id = Column(GUID(), primary_key=True)
    period_days = Column(Integer, nullable=False, default=30)
    fuel_mix = Column(JSON_TYPE, nullable=True)
    avg_fuel_txn_amount = Column(Numeric(14, 2), nullable=True)
    fuel_txn_count = Column(Integer, nullable=True)
    fuel_txn_days_active = Column(Integer, nullable=True)
    geo_regions = Column(JSON_TYPE, nullable=True)
    fleet_type = Column(Text, nullable=True)
    aggressiveness_score = Column(Numeric(6, 4), nullable=True)
    maintenance_risk_score = Column(Numeric(6, 4), nullable=True)
    economy_score = Column(Numeric(6, 4), nullable=True)
    marketplace_affinity = Column(JSON_TYPE, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProductTaxonomy(Base):
    __tablename__ = "product_taxonomy"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    category_code = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=False)
    parent_code = Column(Text, nullable=True)
    tags = Column(JSON_TYPE, nullable=True)


class ProductAttributes(Base):
    __tablename__ = "product_attributes"

    product_id = Column(GUID(), primary_key=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    category_code = Column(Text, nullable=False, index=True)
    tags = Column(JSON_TYPE, nullable=True)
    compatibility = Column(JSON_TYPE, nullable=True)
    meta = Column(JSON_TYPE, nullable=True)


class OfferCandidate(Base):
    __tablename__ = "offer_candidates"
    __table_args__ = (PrimaryKeyConstraint("client_id", "product_id", name="pk_offer_candidates"),)

    tenant_id = Column(GUID(), nullable=True, index=True)
    client_id = Column(GUID(), nullable=False, index=True)
    product_id = Column(GUID(), nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    base_score = Column(Numeric(6, 4), nullable=False, default=0)
    reasons = Column(JSON_TYPE, nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = [
    "ClientBehaviorProfile",
    "MarketplaceEvent",
    "MarketplaceEventType",
    "OfferCandidate",
    "ProductAttributes",
    "ProductTaxonomy",
]
