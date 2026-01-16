from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class SupportTicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"


class SupportTicketPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class SupportTicketSlaStatus(str, Enum):
    OK = "OK"
    BREACHED = "BREACHED"
    PENDING = "PENDING"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(GUID(), nullable=False, index=True)
    created_by_user_id = Column(String(128), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(
        ExistingEnum(SupportTicketStatus, name="support_ticket_status"),
        nullable=False,
        default=SupportTicketStatus.OPEN,
        index=True,
    )
    priority = Column(
        ExistingEnum(SupportTicketPriority, name="support_ticket_priority"),
        nullable=False,
        default=SupportTicketPriority.NORMAL,
        index=True,
    )
    first_response_due_at = Column(DateTime(timezone=True), nullable=True)
    first_response_at = Column(DateTime(timezone=True), nullable=True)
    resolution_due_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    sla_first_response_status = Column(
        ExistingEnum(SupportTicketSlaStatus, name="support_ticket_sla_status"),
        nullable=False,
        default=SupportTicketSlaStatus.PENDING,
    )
    sla_resolution_status = Column(
        ExistingEnum(SupportTicketSlaStatus, name="support_ticket_sla_status"),
        nullable=False,
        default=SupportTicketSlaStatus.PENDING,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (Index("ix_support_tickets_org_creator", "org_id", "created_by_user_id"),)


class SupportTicketComment(Base):
    __tablename__ = "support_ticket_comments"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    ticket_id = Column(
        GUID(),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String(128), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupportTicketAttachment(Base):
    __tablename__ = "support_ticket_attachments"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    ticket_id = Column(
        GUID(),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id = Column(GUID(), nullable=False, index=True)
    uploaded_by_user_id = Column(String(128), nullable=False)
    file_name = Column(String(255), nullable=False)
    content_type = Column(String(128), nullable=False)
    size = Column(Integer, nullable=False)
    object_key = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupportTicketSlaPolicy(Base):
    __tablename__ = "support_ticket_sla_policies"

    org_id = Column(GUID(), primary_key=True)
    first_response_minutes = Column(Integer, nullable=False)
    resolution_minutes = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


__all__ = [
    "SupportTicket",
    "SupportTicketAttachment",
    "SupportTicketComment",
    "SupportTicketPriority",
    "SupportTicketSlaPolicy",
    "SupportTicketSlaStatus",
    "SupportTicketStatus",
]
