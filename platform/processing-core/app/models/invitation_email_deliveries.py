from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.db import Base
from app.db.types import GUID, new_uuid_str


class InvitationEmailDelivery(Base):
    __tablename__ = "invitation_email_deliveries"
    __table_args__ = (
        Index("ix_invitation_email_deliveries_invitation_id", "invitation_id"),
        Index("ix_invitation_email_deliveries_status", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    invitation_id = Column(GUID(), ForeignKey("client_invitations.id"), nullable=False)
    channel = Column(String(16), nullable=False, server_default="EMAIL")
    provider = Column(Text, nullable=False, server_default="integration-hub")
    to_email = Column(Text, nullable=False)
    template = Column(Text, nullable=False)
    subject = Column(Text, nullable=False)
    message_id = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, server_default="QUEUED")
    error_code = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    attempt = Column(Integer, nullable=False, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
