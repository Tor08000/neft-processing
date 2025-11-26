from __future__ import annotations

from sqlalchemy import Column, String

from app.db import Base


class Card(Base):
    __tablename__ = "cards"

    id = Column(String(64), primary_key=True, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    pan_masked = Column(String(32), nullable=True)
    expires_at = Column(String(16), nullable=True)
