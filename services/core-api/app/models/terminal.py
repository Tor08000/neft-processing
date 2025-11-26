from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String

from app.db import Base


class Terminal(Base):
    __tablename__ = "terminals"

    id = Column(String(64), primary_key=True, index=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    location = Column(String(255), nullable=True)
