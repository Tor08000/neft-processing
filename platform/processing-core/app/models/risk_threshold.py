from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.models.risk_score import RiskLevel
from app.models.risk_types import RiskDecisionType, RiskSubjectType

class RiskThreshold(Base):
    __tablename__ = "risk_thresholds"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    threshold_set_id = Column(String(64), nullable=False)
    subject_type = Column(ExistingEnum(RiskSubjectType, name="risksubjecttype"), nullable=False)

    min_score = Column(Integer, nullable=False)
    max_score = Column(Integer, nullable=False)

    risk_level = Column(ExistingEnum(RiskLevel, name="risklevel"), nullable=False)
    outcome = Column(ExistingEnum(RiskDecisionType, name="riskdecision"), nullable=False)

    requires_manual_review = Column(Boolean, nullable=False, default=False)
    priority = Column(Integer, nullable=False, default=100)
    active = Column(Boolean, nullable=False, default=True)

    valid_from = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    valid_to = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_risk_thresholds_set", "threshold_set_id"),
        Index("ix_risk_thresholds_priority", "priority"),
        Index("ix_risk_thresholds_subject", "subject_type"),
        Index("ix_risk_thresholds_active", "active"),
    )


__all__ = ["RiskThreshold"]
