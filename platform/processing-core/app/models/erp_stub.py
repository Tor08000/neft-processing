from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str

JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class ErpStubExportType(str, Enum):
    INVOICES = "INVOICES"
    PAYMENTS = "PAYMENTS"
    SETTLEMENT = "SETTLEMENT"
    RECONCILIATION = "RECONCILIATION"


class ErpStubExportStatus(str, Enum):
    CREATED = "CREATED"
    SENT = "SENT"
    ACKED = "ACKED"
    FAILED = "FAILED"


class ErpStubExport(Base):
    __tablename__ = "erp_stub_exports"
    __table_args__ = (
        UniqueConstraint("export_ref", name="uq_erp_stub_exports_ref"),
        Index("ix_erp_stub_exports_tenant_status", "tenant_id", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    export_ref = Column(String(128), nullable=False)
    export_type = Column(ExistingEnum(ErpStubExportType, name="erp_stub_export_type"), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    status = Column(ExistingEnum(ErpStubExportStatus, name="erp_stub_export_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    items = relationship(
        "ErpStubExportItem",
        back_populates="export",
        cascade="all, delete-orphan",
    )


class ErpStubExportItem(Base):
    __tablename__ = "erp_stub_export_items"
    __table_args__ = (
        Index("ix_erp_stub_export_items_export", "export_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    export_id = Column(GUID(), ForeignKey("erp_stub_exports.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    snapshot_json = Column(JSON_TYPE, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    export = relationship("ErpStubExport", back_populates="items")


__all__ = [
    "ErpStubExport",
    "ErpStubExportItem",
    "ErpStubExportStatus",
    "ErpStubExportType",
]
