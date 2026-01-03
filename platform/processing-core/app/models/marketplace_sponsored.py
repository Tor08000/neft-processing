from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class SponsoredCampaignStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ENDED = "ENDED"
    EXHAUSTED = "EXHAUSTED"


class SponsoredCampaignObjective(str, Enum):
    CPC = "CPC"
    CPA = "CPA"


class SponsoredEventType(str, Enum):
    IMPRESSION = "IMPRESSION"
    CLICK = "CLICK"
    CONVERSION = "CONVERSION"


class SponsoredSpendType(str, Enum):
    CPC_CLICK = "CPC_CLICK"
    CPA_ORDER = "CPA_ORDER"


class SponsoredSpendDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class SponsoredCampaign(Base):
    __tablename__ = "sponsored_campaigns"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    title = Column(Text, nullable=False)
    status = Column(
        ExistingEnum(SponsoredCampaignStatus, name="sponsored_campaign_status"),
        nullable=False,
        default=SponsoredCampaignStatus.DRAFT.value,
    )
    objective = Column(
        ExistingEnum(SponsoredCampaignObjective, name="sponsored_campaign_objective"),
        nullable=False,
    )
    currency = Column(Text, nullable=False, server_default="RUB")
    targeting = Column(JSON_TYPE, nullable=False)
    scope = Column(JSON_TYPE, nullable=False)
    bid = Column(Numeric(18, 4), nullable=False)
    daily_cap = Column(Numeric(18, 4), nullable=True)
    total_budget = Column(Numeric(18, 4), nullable=False)
    spent_budget = Column(Numeric(18, 4), nullable=False, server_default="0")
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SponsoredEvent(Base):
    __tablename__ = "sponsored_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=False, index=True)
    campaign_id = Column(GUID(), ForeignKey("sponsored_campaigns.id", ondelete="RESTRICT"), nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    client_id = Column(GUID(), nullable=True, index=True)
    user_id = Column(GUID(), nullable=True, index=True)
    product_id = Column(GUID(), nullable=True, index=True)
    event_type = Column(
        ExistingEnum(SponsoredEventType, name="sponsored_event_type"),
        nullable=False,
    )
    event_ts = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    context = Column(JSON_TYPE, nullable=False)
    meta = Column(JSON_TYPE, nullable=True)


class SponsoredSpendLedger(Base):
    __tablename__ = "sponsored_spend_ledger"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=False, index=True)
    campaign_id = Column(GUID(), ForeignKey("sponsored_campaigns.id", ondelete="RESTRICT"), nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    spend_type = Column(
        ExistingEnum(SponsoredSpendType, name="sponsored_spend_type"),
        nullable=False,
    )
    amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(Text, nullable=False)
    ref_type = Column(Text, nullable=False)
    ref_id = Column(GUID(), nullable=False, index=True)
    direction = Column(
        ExistingEnum(SponsoredSpendDirection, name="sponsored_spend_direction"),
        nullable=False,
        server_default=SponsoredSpendDirection.DEBIT.value,
    )
    reversal_of = Column(GUID(), ForeignKey("sponsored_spend_ledger.id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = [
    "SponsoredCampaign",
    "SponsoredCampaignObjective",
    "SponsoredCampaignStatus",
    "SponsoredEvent",
    "SponsoredEventType",
    "SponsoredSpendDirection",
    "SponsoredSpendLedger",
    "SponsoredSpendType",
]
