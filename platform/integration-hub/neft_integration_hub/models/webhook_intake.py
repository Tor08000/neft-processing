from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, Index, String, func
from sqlalchemy.orm import Mapped

from neft_integration_hub.db import Base


class WebhookIntakeEvent(Base):
    __tablename__ = "webhook_intake_events"
    __table_args__ = (Index("ix_webhook_intake_events_source", "source", "created_at"),)

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = Column(String(32), nullable=False)
    event_type: Mapped[str] = Column(String(128), nullable=False)
    event_id: Mapped[str | None] = Column(String(64), nullable=True)
    payload: Mapped[dict] = Column(JSON, nullable=False)
    signature: Mapped[str | None] = Column(String(256), nullable=True)
    verified: Mapped[bool] = Column(Boolean, nullable=False, default=False)
    request_id: Mapped[str | None] = Column(String(64), nullable=True)
    trace_id: Mapped[str | None] = Column(String(64), nullable=True)

    created_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["WebhookIntakeEvent"]
