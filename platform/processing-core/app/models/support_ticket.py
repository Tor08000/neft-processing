from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, func

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


__all__ = [
    "SupportTicket",
    "SupportTicketComment",
    "SupportTicketPriority",
    "SupportTicketStatus",
]
