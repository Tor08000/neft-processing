from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.sql import func

from app.db import Base
from app.db.types import GUID, new_uuid_str


class ClientInvitation(Base):
    __tablename__ = "client_invitations"
    __table_args__ = (
        Index("ix_client_invitations_client_status", "client_id", "status"),
        Index("ix_client_invitations_email", "email"),
        Index("ix_client_invitations_email_lower", text("lower(email)")),
        Index("ix_client_invitations_expires_at", "expires_at"),
        UniqueConstraint("token_hash", name="uq_client_invitations_token_hash"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    email = Column(String(256), nullable=False)
    invited_by_user_id = Column(String(64), nullable=False)
    created_by_user_id = Column(String(64), nullable=True)
    roles = Column(JSON, nullable=False, default=list)
    token_hash = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), nullable=False, server_default="PENDING")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by_user_id = Column(String(64), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id = Column(String(64), nullable=True)
    revocation_reason = Column(Text, nullable=True)
    resent_count = Column(Integer, nullable=False, server_default="0")
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    last_send_status = Column(String(32), nullable=True)
    last_send_error = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
