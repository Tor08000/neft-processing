from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.sql import func

from app.db import Base


class Card(Base):
    __tablename__ = "cards"

    id = Column(String(64), primary_key=True, index=True)
    client_id = Column(String(64), ForeignKey("clients.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    pan_masked = Column(String(32), nullable=True)
    external_id = Column(String(128), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(String(16), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
