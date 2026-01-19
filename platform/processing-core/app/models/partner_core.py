from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSONB_TYPE = postgresql.JSONB(none_as_null=True)
JSON_TYPE = JSON().with_variant(JSONB_TYPE, "postgresql")


class PartnerProfileStatus(str, Enum):
    ONBOARDING = "ONBOARDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class PartnerOfferStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class PartnerOrderStatus(str, Enum):
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class PartnerProfile(Base):
    __tablename__ = "partner_profiles"
    __table_args__ = (UniqueConstraint("org_id", name="uq_partner_profiles_org_id"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(BigInteger, ForeignKey("orgs.id"), nullable=False, index=True)
    status = Column(
        ExistingEnum(PartnerProfileStatus, name="partner_profile_status"),
        nullable=False,
        server_default=PartnerProfileStatus.ONBOARDING.value,
    )
    display_name = Column(String(255), nullable=True)
    contacts_json = Column(JSON_TYPE, nullable=True)
    meta_json = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PartnerOffer(Base):
    __tablename__ = "partner_offers"
    __table_args__ = (
        UniqueConstraint("org_id", "code", name="uq_partner_offers_org_code"),
        Index("ix_partner_offers_org_status", "org_id", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(BigInteger, ForeignKey("orgs.id"), nullable=False, index=True)
    code = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    base_price = Column(Numeric(18, 2), nullable=True)
    currency = Column(String(8), nullable=False, server_default="RUB")
    status = Column(
        ExistingEnum(PartnerOfferStatus, name="partner_offer_status"),
        nullable=False,
        server_default=PartnerOfferStatus.INACTIVE.value,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PartnerOrder(Base):
    __tablename__ = "partner_orders"
    __table_args__ = (Index("ix_partner_orders_partner_status", "partner_org_id", "status"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_org_id = Column(BigInteger, nullable=False, index=True)
    client_org_id = Column(BigInteger, nullable=True, index=True)
    offer_id = Column(GUID(), nullable=True)
    title = Column(String(255), nullable=False)
    status = Column(
        ExistingEnum(PartnerOrderStatus, name="partner_order_status"),
        nullable=False,
        server_default=PartnerOrderStatus.NEW.value,
    )
    response_due_at = Column(DateTime(timezone=True), nullable=True)
    resolution_due_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


__all__ = [
    "PartnerOffer",
    "PartnerOfferStatus",
    "PartnerOrder",
    "PartnerOrderStatus",
    "PartnerProfile",
    "PartnerProfileStatus",
]
