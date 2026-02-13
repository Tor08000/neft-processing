from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.db import Base


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(32), nullable=False, index=True)
    subject_id = Column(String(128), nullable=False, index=True)
    selector = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    window = Column(String(32), nullable=True)
    metric = Column(String(32), nullable=True)
    policy = Column(String(32), nullable=False)
    meta = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    priority = Column(Integer, nullable=False, default=100)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    system = Column(Boolean, nullable=False, default=False, index=True)
    name = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)
