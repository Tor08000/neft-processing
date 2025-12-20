from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base


class PayoutEvent(Base):
    __tablename__ = "payout_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    payout_order_id = Column(String(36), ForeignKey("payout_orders.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    payout_order = relationship("PayoutOrder", back_populates="events")


__all__ = ["PayoutEvent"]
