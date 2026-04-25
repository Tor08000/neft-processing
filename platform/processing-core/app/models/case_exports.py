from __future__ import annotations

from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, Index, String, Text, func

from app.db import Base
from app.db.types import ExistingEnum, new_uuid_str


class CaseExportKind(str, Enum):
    EXPLAIN = "EXPLAIN"
    DIFF = "DIFF"
    CASE = "CASE"


class CaseExport(Base):
    __tablename__ = "case_exports"
    __table_args__ = (
        Index("ix_case_exports_case_created", "case_id", "created_at"),
        Index("ix_case_exports_kind_created", "kind", "created_at"),
        Index("ix_case_exports_active", "deleted_at"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    case_id = Column(String(36), nullable=True, index=True)
    kind = Column(ExistingEnum(CaseExportKind, name="case_export_kind"), nullable=False)
    object_key = Column(Text, nullable=False, unique=True)
    content_type = Column(String(128), nullable=False)
    content_sha256 = Column(String(64), nullable=False)
    artifact_signature = Column(Text, nullable=True)
    artifact_signature_alg = Column(String(64), nullable=True)
    artifact_signing_key_id = Column(String(256), nullable=True)
    artifact_signed_at = Column(DateTime(timezone=True), nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_user_id = Column(String(36), nullable=True)
    request_id = Column(String(128), nullable=True)
    trace_id = Column(String(128), nullable=True)
    retention_until = Column(DateTime(timezone=True), nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    delete_reason = Column(Text, nullable=True)


__all__ = ["CaseExport", "CaseExportKind"]
