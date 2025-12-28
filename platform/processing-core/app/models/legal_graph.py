from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class LegalNodeType(str, Enum):
    DOCUMENT = "DOCUMENT"
    DOCUMENT_FILE = "DOCUMENT_FILE"
    DOCUMENT_ACK = "DOCUMENT_ACK"
    CLOSING_PACKAGE = "CLOSING_PACKAGE"
    BILLING_PERIOD = "BILLING_PERIOD"
    INVOICE = "INVOICE"
    SUBSCRIPTION = "SUBSCRIPTION"
    PAYMENT = "PAYMENT"
    CREDIT_NOTE = "CREDIT_NOTE"
    REFUND = "REFUND"
    SETTLEMENT_ALLOCATION = "SETTLEMENT_ALLOCATION"
    ACCOUNTING_EXPORT_BATCH = "ACCOUNTING_EXPORT_BATCH"
    RISK_DECISION = "RISK_DECISION"
    OFFER = "OFFER"
    FUEL_TRANSACTION = "FUEL_TRANSACTION"
    CARD = "CARD"
    FUEL_STATION = "FUEL_STATION"
    VEHICLE = "VEHICLE"
    DRIVER = "DRIVER"
    FUEL_LIMIT = "FUEL_LIMIT"
    LOGISTICS_ORDER = "LOGISTICS_ORDER"
    LOGISTICS_ROUTE = "LOGISTICS_ROUTE"
    LOGISTICS_STOP = "LOGISTICS_STOP"


class LegalEdgeType(str, Enum):
    GENERATED_FROM = "GENERATED_FROM"
    CONFIRMS = "CONFIRMS"
    CLOSES = "CLOSES"
    INCLUDES = "INCLUDES"
    RELATES_TO = "RELATES_TO"
    SIGNED_BY = "SIGNED_BY"
    RISK_GATED_BY = "RISK_GATED_BY"
    GATED_BY_RISK = "GATED_BY_RISK"
    SETTLES = "SETTLES"
    EXPORTS = "EXPORTS"
    REPLACES = "REPLACES"
    ALLOCATES = "ALLOCATES"
    OVERRIDDEN_BY = "OVERRIDDEN_BY"


class LegalGraphSnapshotScopeType(str, Enum):
    DOCUMENT = "DOCUMENT"
    CLOSING_PACKAGE = "CLOSING_PACKAGE"
    BILLING_PERIOD = "BILLING_PERIOD"


class LegalNode(Base):
    __tablename__ = "legal_nodes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "node_type", "ref_id", name="uq_legal_nodes_scope"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    node_type = Column(ExistingEnum(LegalNodeType, name="legal_node_type"), nullable=False)
    ref_id = Column(String(128), nullable=False)
    ref_table = Column(String(64), nullable=True)
    hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LegalEdge(Base):
    __tablename__ = "legal_edges"
    __table_args__ = (
        UniqueConstraint("tenant_id", "edge_type", "src_node_id", "dst_node_id", name="uq_legal_edges_scope"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    edge_type = Column(ExistingEnum(LegalEdgeType, name="legal_edge_type"), nullable=False)
    src_node_id = Column(GUID(), ForeignKey("legal_nodes.id"), nullable=False)
    dst_node_id = Column(GUID(), ForeignKey("legal_nodes.id"), nullable=False)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LegalGraphSnapshot(Base):
    __tablename__ = "legal_graph_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "scope_type",
            "scope_ref_id",
            "snapshot_hash",
            name="uq_legal_graph_snapshots_scope",
        ),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    scope_type = Column(ExistingEnum(LegalGraphSnapshotScopeType, name="legal_graph_snapshot_scope"), nullable=False)
    scope_ref_id = Column(String(128), nullable=False)
    snapshot_hash = Column(String(64), nullable=False)
    nodes_count = Column(Integer, nullable=False, default=0, server_default="0")
    edges_count = Column(Integer, nullable=False, default=0, server_default="0")
    snapshot_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_actor_type = Column(String(32), nullable=True)
    created_by_actor_id = Column(String(64), nullable=True)


__all__ = [
    "LegalNode",
    "LegalEdge",
    "LegalGraphSnapshot",
    "LegalNodeType",
    "LegalEdgeType",
    "LegalGraphSnapshotScopeType",
]
