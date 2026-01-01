from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, func

from app.db import Base
from app.db.types import GUID, new_uuid_str


class AuditLegalHoldScope(str, Enum):
    CASE = "case"
    ORG = "org"
    GLOBAL = "global"


class AuditLegalHold(Base):
    __tablename__ = "audit_legal_holds"
    __table_args__ = (Index("ix_audit_legal_holds_active_case", "active", "case_id"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    scope = Column(String(16), nullable=False)
    case_id = Column(GUID(), nullable=True)
    reason = Column(Text, nullable=False)
    created_by = Column(GUID(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    active = Column(Boolean, nullable=False, default=True)


class AuditPurgeLog(Base):
    __tablename__ = "audit_purge_log"
    __table_args__ = (Index("ix_audit_purge_log_case_purged", "case_id", "purged_at"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(128), nullable=False)
    case_id = Column(GUID(), nullable=True)
    policy = Column(String(128), nullable=False)
    retention_days = Column(Integer, nullable=False)
    purged_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    purged_by = Column(String(128), nullable=False)
    reason = Column(Text, nullable=True)
    prev_tail_hash = Column(Text, nullable=True)
    note = Column(Text, nullable=True)


__all__ = ["AuditLegalHold", "AuditLegalHoldScope", "AuditPurgeLog"]
