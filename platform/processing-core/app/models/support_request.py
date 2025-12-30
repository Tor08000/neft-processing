from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class SupportRequestScopeType(str, Enum):
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"


class SupportRequestSubjectType(str, Enum):
    ORDER = "ORDER"
    DOCUMENT = "DOCUMENT"
    PAYOUT = "PAYOUT"
    SETTLEMENT = "SETTLEMENT"
    INTEGRATION = "INTEGRATION"
    OTHER = "OTHER"


class SupportRequestStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING = "WAITING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class SupportRequestPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class SupportRequest(Base):
    __tablename__ = "support_requests"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=True, index=True)
    partner_id = Column(String(64), nullable=True, index=True)
    created_by_user_id = Column(Text, nullable=True)
    scope_type = Column(
        ExistingEnum(SupportRequestScopeType, name="support_request_scope_type"),
        nullable=False,
        index=True,
    )
    subject_type = Column(
        ExistingEnum(SupportRequestSubjectType, name="support_request_subject_type"),
        nullable=False,
        index=True,
    )
    subject_id = Column(GUID(), nullable=True, index=True)
    correlation_id = Column(String(128), nullable=True)
    event_id = Column(GUID(), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(
        ExistingEnum(SupportRequestStatus, name="support_request_status"),
        nullable=False,
        default=SupportRequestStatus.OPEN,
        index=True,
    )
    priority = Column(
        ExistingEnum(SupportRequestPriority, name="support_request_priority"),
        nullable=False,
        default=SupportRequestPriority.NORMAL,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_support_requests_subject", "subject_type", "subject_id"),)


__all__ = [
    "SupportRequest",
    "SupportRequestPriority",
    "SupportRequestScopeType",
    "SupportRequestStatus",
    "SupportRequestSubjectType",
]
