from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String

from app.db import Base
from app.db.types import ExistingEnum
from app.models.risk_types import RiskSubjectType


class RiskThresholdSet(Base):
    __tablename__ = "risk_threshold_sets"

    id = Column(String(64), primary_key=True)
    subject_type = Column(ExistingEnum(RiskSubjectType, name="risksubjecttype"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_risk_threshold_sets_subject", "subject_type"),
        Index("ix_risk_threshold_sets_active", "active"),
    )


__all__ = ["RiskThresholdSet"]
