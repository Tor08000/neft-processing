from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, Date, DateTime, Index, Numeric, String, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, new_uuid_str


JSONB_TYPE = postgresql.JSONB(none_as_null=True)
JSON_TYPE = JSON().with_variant(JSONB_TYPE, "postgresql")


class PartnerLedgerEntryType(str, Enum):
    EARNED = "EARNED"
    SLA_PENALTY = "SLA_PENALTY"
    ADJUSTMENT = "ADJUSTMENT"
    PAYOUT_REQUESTED = "PAYOUT_REQUESTED"
    PAYOUT_APPROVED = "PAYOUT_APPROVED"
    PAYOUT_PAID = "PAYOUT_PAID"


class PartnerLedgerDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class PartnerPayoutRequestStatus(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"


class PartnerDocumentStatus(str, Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PAID = "PAID"


class PartnerAccount(Base):
    __tablename__ = "partner_accounts"

    org_id = Column(String(64), primary_key=True)
    currency = Column(String(8), nullable=False, server_default="RUB")
    balance_available = Column(Numeric(18, 4), nullable=False, server_default="0")
    balance_pending = Column(Numeric(18, 4), nullable=False, server_default="0")
    balance_blocked = Column(Numeric(18, 4), nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PartnerLedgerEntry(Base):
    __tablename__ = "partner_ledger_entries"
    __table_args__ = (
        Index("ix_partner_ledger_partner_created", "partner_org_id", "created_at"),
        Index("ix_partner_ledger_order", "order_id"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    partner_org_id = Column(String(64), nullable=False, index=True)
    order_id = Column(String(64), nullable=True, index=True)
    entry_type = Column(ExistingEnum(PartnerLedgerEntryType, name="partner_ledger_entry_type"), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(8), nullable=False)
    direction = Column(ExistingEnum(PartnerLedgerDirection, name="partner_ledger_direction"), nullable=False)
    meta_json = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PartnerPayoutRequest(Base):
    __tablename__ = "partner_payout_requests"
    __table_args__ = (Index("ix_partner_payout_partner_status", "partner_org_id", "status"),)

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    partner_org_id = Column(String(64), nullable=False, index=True)
    amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(8), nullable=False)
    status = Column(
        ExistingEnum(PartnerPayoutRequestStatus, name="partner_payout_request_status"),
        nullable=False,
        server_default=PartnerPayoutRequestStatus.REQUESTED.value,
    )
    requested_by = Column(String(64), nullable=True)
    approved_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)


class PartnerInvoice(Base):
    __tablename__ = "partner_invoices"
    __table_args__ = (Index("ix_partner_invoices_partner_period", "partner_org_id", "period_from", "period_to"),)

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    partner_org_id = Column(String(64), nullable=False, index=True)
    period_from = Column(Date, nullable=False)
    period_to = Column(Date, nullable=False)
    total_amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(8), nullable=False)
    status = Column(
        ExistingEnum(PartnerDocumentStatus, name="partner_document_status"),
        nullable=False,
        server_default=PartnerDocumentStatus.DRAFT.value,
    )
    tax_context = Column(JSON_TYPE, nullable=True)
    pdf_object_key = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PartnerAct(Base):
    __tablename__ = "partner_acts"
    __table_args__ = (Index("ix_partner_acts_partner_period", "partner_org_id", "period_from", "period_to"),)

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    partner_org_id = Column(String(64), nullable=False, index=True)
    period_from = Column(Date, nullable=False)
    period_to = Column(Date, nullable=False)
    total_amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(8), nullable=False)
    status = Column(
        ExistingEnum(PartnerDocumentStatus, name="partner_document_status"),
        nullable=False,
        server_default=PartnerDocumentStatus.DRAFT.value,
    )
    tax_context = Column(JSON_TYPE, nullable=True)
    pdf_object_key = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


__all__ = [
    "PartnerAccount",
    "PartnerAct",
    "PartnerDocumentStatus",
    "PartnerInvoice",
    "PartnerLedgerDirection",
    "PartnerLedgerEntry",
    "PartnerLedgerEntryType",
    "PartnerPayoutRequest",
    "PartnerPayoutRequestStatus",
]
