from __future__ import annotations

from sqlalchemy import Boolean, Column, String

from app.db import Base


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    key = Column(String(128), primary_key=True)
    on = Column(Boolean, nullable=False, server_default="false")
    segment = Column(String(128), nullable=True)


__all__ = ["FeatureFlag"]
