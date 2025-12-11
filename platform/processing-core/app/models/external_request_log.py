from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.db import Base


class ExternalRequestLog(Base):
    __tablename__ = "external_request_logs"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(String(64), index=True, nullable=False)
    azs_id = Column(String(64), index=True, nullable=True)
    terminal_id = Column(String(64), nullable=True)
    operation_id = Column(String(128), nullable=True)
    request_type = Column(String(32), nullable=False)
    amount = Column(Integer, nullable=True)
    liters = Column(Float, nullable=True)
    currency = Column(String(8), nullable=True)
    status = Column(String(32), index=True, nullable=False)
    reason_category = Column(String(32), index=True, nullable=True)
    risk_code = Column(String(64), nullable=True)
    limit_code = Column(String(64), nullable=True)
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

