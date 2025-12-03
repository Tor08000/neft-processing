from __future__ import annotations

from sqlalchemy import Column, String

from app.db import Base


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, index=True)
