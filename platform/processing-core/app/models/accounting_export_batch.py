from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import foreign, relationship

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class AccountingExportType(str, Enum):
    CHARGES = "CHARGES"
    SETTLEMENT = "SETTLEMENT"


class AccountingExportFormat(str, Enum):
    CSV = "CSV"
    JSON = "JSON"


class AccountingExportState(str, Enum):
    CREATED = "CREATED"
    GENERATED = "GENERATED"
    UPLOADED = "UPLOADED"
    DOWNLOADED = "DOWNLOADED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class AccountingExportBatch(Base):
    __tablename__ = "accounting_export_batches"
    __table_args__ = (
        Index("ix_accounting_export_batches_period", "billing_period_id"),
        Index("ix_accounting_export_batches_state", "state"),
        Index("ix_accounting_export_batches_type_format", "export_type", "format"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    billing_period_id = Column(GUID(), nullable=False, index=True)
    export_type = Column(ExistingEnum(AccountingExportType, name="accounting_export_type"), nullable=False)
    format = Column(ExistingEnum(AccountingExportFormat, name="accounting_export_format"), nullable=False)
    state = Column(ExistingEnum(AccountingExportState, name="accounting_export_state"), nullable=False)
    idempotency_key = Column(String(128), nullable=False, unique=True)
    checksum_sha256 = Column(String(64), nullable=True)
    records_count = Column(Integer, nullable=False, server_default="0", default=0)
    object_key = Column(Text, nullable=True)
    bucket = Column(String(128), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    downloaded_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    billing_period = relationship(
        "BillingPeriod",
        primaryjoin="BillingPeriod.id == foreign(AccountingExportBatch.billing_period_id)",
        backref="accounting_export_batches",
        viewonly=True,
    )


__all__ = [
    "AccountingExportBatch",
    "AccountingExportFormat",
    "AccountingExportState",
    "AccountingExportType",
]
