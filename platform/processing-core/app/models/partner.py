from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, String

from app.db import Base


class Partner(Base):
    __tablename__ = "partners"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(32), nullable=False)
    allowed_ips = Column(JSON, default=list)
    token = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
