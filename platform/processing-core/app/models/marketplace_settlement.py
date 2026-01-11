from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Numeric, String, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class MarketplaceSettlementStatus(str, Enum):
    OPEN = "OPEN"
    INCLUDED_IN_PAYOUT = "INCLUDED_IN_PAYOUT"
    SETTLED = "SETTLED"


class MarketplaceAdjustmentType(str, Enum):
    PENALTY = "PENALTY"
    CREDIT_NOTE = "CREDIT_NOTE"
    MANUAL_DEBIT = "MANUAL_DEBIT"
    MANUAL_CREDIT = "MANUAL_CREDIT"


class MarketplaceSettlementItem(Base):
    __tablename__ = "marketplace_settlement_items"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(GUID(), nullable=False, index=True)
    period = Column(String(7), nullable=False, index=True)
    gross_amount = Column(Numeric(18, 4), nullable=False)
    commission_amount = Column(Numeric(18, 4), nullable=False)
    net_partner_amount = Column(Numeric(18, 4), nullable=False)
    penalty_amount = Column(Numeric(18, 4), nullable=False, default=0)
    adjustments_amount = Column(Numeric(18, 4), nullable=False, default=0)
    status = Column(
        ExistingEnum(MarketplaceSettlementStatus, name="marketplace_settlement_status"),
        nullable=False,
        default=MarketplaceSettlementStatus.OPEN.value,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MarketplaceAdjustment(Base):
    __tablename__ = "marketplace_adjustments"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_id = Column(GUID(), nullable=False, index=True)
    order_id = Column(GUID(), nullable=True, index=True)
    period = Column(String(7), nullable=False, index=True)
    type = Column(
        ExistingEnum(MarketplaceAdjustmentType, name="marketplace_adjustment_type"),
        nullable=False,
    )
    amount = Column(Numeric(18, 4), nullable=False)
    reason_code = Column(Text, nullable=True)
    meta = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = [
    "MarketplaceAdjustment",
    "MarketplaceAdjustmentType",
    "MarketplaceSettlementItem",
    "MarketplaceSettlementStatus",
]
