from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import BigInteger, Column, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.db import Base


json_variant = JSON().with_variant(postgresql.JSONB, "postgresql")


class PayoutExportFormat(str, Enum):
    CSV = "CSV"
    XLSX = "XLSX"


class PayoutExportState(str, Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    UPLOADED = "UPLOADED"
    FAILED = "FAILED"
    STALE = "STALE"


class PayoutExportFile(Base):
    __tablename__ = "payout_export_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    batch_id = Column(String(36), ForeignKey("payout_batches.id"), nullable=False, index=True)
    format = Column(SAEnum(PayoutExportFormat, name="payout_export_format"), nullable=False)
    state = Column(SAEnum(PayoutExportState, name="payout_export_state"), nullable=False)
    provider = Column(String(64), nullable=True)
    external_ref = Column(String(128), nullable=True)
    bank_format_code = Column(String(64), nullable=True)
    object_key = Column(String(512), nullable=False)
    bucket = Column(String(128), nullable=False)
    sha256 = Column(String(64), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String(512), nullable=True)
    meta = Column(json_variant, nullable=True)

    batch = relationship("PayoutBatch", backref="exports")


__all__ = [
    "PayoutExportFile",
    "PayoutExportFormat",
    "PayoutExportState",
]
