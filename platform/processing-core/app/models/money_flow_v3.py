from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, Index, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.services.money_flow.states import MoneyFlowType


class MoneyFlowLinkNodeType(str, Enum):
    SUBSCRIPTION = "SUBSCRIPTION"
    SUBSCRIPTION_SEGMENT = "SUBSCRIPTION_SEGMENT"
    SUBSCRIPTION_CHARGE = "SUBSCRIPTION_CHARGE"
    USAGE_COUNTER = "USAGE_COUNTER"
    INVOICE = "INVOICE"
    DOCUMENT = "DOCUMENT"
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    FUEL_TX = "FUEL_TX"
    LOGISTICS_ORDER = "LOGISTICS_ORDER"
    ACCOUNTING_EXPORT = "ACCOUNTING_EXPORT"
    LEDGER_TX = "LEDGER_TX"
    BILLING_PERIOD = "BILLING_PERIOD"


class MoneyFlowLinkType(str, Enum):
    GENERATES = "GENERATES"
    SETTLES = "SETTLES"
    POSTS = "POSTS"
    FEEDS = "FEEDS"
    RELATES = "RELATES"


class MoneyInvariantSnapshotPhase(str, Enum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"


class MoneyFlowLink(Base):
    __tablename__ = "money_flow_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "src_type",
            "src_id",
            "link_type",
            "dst_type",
            "dst_id",
            name="uq_money_flow_links_scope",
        ),
        Index("ix_money_flow_links_src", "src_type", "src_id"),
        Index("ix_money_flow_links_dst", "dst_type", "dst_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=False)
    src_type = Column(ExistingEnum(MoneyFlowLinkNodeType, name="money_flow_link_node_type"), nullable=False)
    src_id = Column(String(128), nullable=False)
    dst_type = Column(ExistingEnum(MoneyFlowLinkNodeType, name="money_flow_link_node_type"), nullable=False)
    dst_id = Column(String(128), nullable=False)
    link_type = Column(ExistingEnum(MoneyFlowLinkType, name="money_flow_link_type"), nullable=False)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MoneyInvariantSnapshot(Base):
    __tablename__ = "money_invariant_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "phase",
            "snapshot_hash",
            name="uq_money_invariant_snapshots_scope",
        ),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=False)
    flow_type = Column(ExistingEnum(MoneyFlowType, name="money_flow_type"), nullable=False)
    flow_ref_id = Column(String(64), nullable=False)
    event_id = Column(GUID(), ForeignKey("money_flow_events.id"), nullable=False)
    phase = Column(ExistingEnum(MoneyInvariantSnapshotPhase, name="money_invariant_snapshot_phase"), nullable=False)
    snapshot_hash = Column(String(64), nullable=False)
    snapshot_json = Column(JSON, nullable=False)
    passed = Column(Boolean, nullable=False, default=True, server_default="true")
    violations = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "MoneyFlowLink",
    "MoneyInvariantSnapshot",
    "MoneyFlowLinkNodeType",
    "MoneyFlowLinkType",
    "MoneyInvariantSnapshotPhase",
]
