from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class SettlementAccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class SettlementPeriodStatus(str, Enum):
    OPEN = "OPEN"
    CALCULATED = "CALCULATED"
    APPROVED = "APPROVED"
    PAID = "PAID"


class SettlementItemSourceType(str, Enum):
    INVOICE = "invoice"
    PAYMENT = "payment"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class SettlementItemDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"


class PayoutStatus(str, Enum):
    INITIATED = "INITIATED"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class SettlementAccount(Base):
    __tablename__ = "settlement_accounts"
    __table_args__ = (UniqueConstraint("partner_id", "currency", name="uq_settlement_accounts_partner_currency"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_id = Column(GUID(), nullable=False)
    currency = Column(String(8), nullable=False)
    status = Column(
        ExistingEnum(SettlementAccountStatus, name="settlement_account_status"),
        nullable=False,
        default=SettlementAccountStatus.ACTIVE,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SettlementPeriod(Base):
    __tablename__ = "settlement_periods"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_id = Column(GUID(), nullable=False)
    currency = Column(String(8), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        ExistingEnum(SettlementPeriodStatus, name="settlement_period_status"),
        nullable=False,
        default=SettlementPeriodStatus.OPEN,
    )
    total_gross = Column(Numeric(18, 4), nullable=False, server_default="0")
    total_fees = Column(Numeric(18, 4), nullable=False, server_default="0")
    total_refunds = Column(Numeric(18, 4), nullable=False, server_default="0")
    net_amount = Column(Numeric(18, 4), nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    audit_event_id = Column(GUID(), nullable=True)


class SettlementItem(Base):
    __tablename__ = "settlement_items"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    settlement_period_id = Column(
        GUID(),
        ForeignKey("settlement_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type = Column(ExistingEnum(SettlementItemSourceType, name="settlement_item_source_type"), nullable=False)
    source_id = Column(GUID(), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    direction = Column(
        ExistingEnum(SettlementItemDirection, name="settlement_item_direction"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SettlementPayout(Base):
    __tablename__ = "payouts"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    settlement_period_id = Column(GUID(), ForeignKey("settlement_periods.id", ondelete="CASCADE"), nullable=False)
    partner_id = Column(GUID(), nullable=False)
    currency = Column(String(8), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    status = Column(
        ExistingEnum(PayoutStatus, name="payout_status"),
        nullable=False,
        default=PayoutStatus.INITIATED,
    )
    provider = Column(String(64), nullable=False)
    provider_payout_id = Column(String(128), nullable=True)
    idempotency_key = Column(String(128), nullable=False, unique=True)
    ledger_tx_id = Column(GUID(), nullable=True)
    audit_event_id = Column(GUID(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "PayoutStatus",
    "SettlementAccount",
    "SettlementAccountStatus",
    "SettlementItem",
    "SettlementItemDirection",
    "SettlementItemSourceType",
    "SettlementPeriod",
    "SettlementPeriodStatus",
    "SettlementPayout",
]
