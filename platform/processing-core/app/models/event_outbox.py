from __future__ import annotations

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import GUID, new_uuid_str


class EventOutbox(Base):
    __tablename__ = "event_outbox"
    __table_args__ = (
        Index("uq_event_outbox_idempotency", "idempotency_key", unique=True),
        Index("idx_event_outbox_pending", "status", "next_attempt_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    aggregate_type = Column(String(), nullable=False)
    aggregate_id = Column(String(), nullable=False)
    event_type = Column(String(), nullable=False)
    payload = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    idempotency_key = Column(String(), nullable=False)
    status = Column(String(), nullable=False, default="pending", server_default="pending")
    retries = Column(Integer(), nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    error = Column(Text(), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)


__all__ = ["EventOutbox"]
