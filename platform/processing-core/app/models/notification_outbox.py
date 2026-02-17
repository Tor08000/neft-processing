from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db import Base
from app.db.types import GUID, new_uuid_str


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        Index("ix_notification_outbox_status_retry", "status", "next_attempt_at"),
        Index("ix_notification_outbox_aggregate", "aggregate_type", "aggregate_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    event_type = Column(Text, nullable=False)
    aggregate_type = Column(Text, nullable=False, server_default="client_invitation")
    aggregate_id = Column(GUID(), nullable=False)
    tenant_client_id = Column(GUID(), nullable=True, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    status = Column(String(16), nullable=False, server_default="NEW", index=True)
    attempts = Column(Integer, nullable=False, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
