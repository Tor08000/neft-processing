from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String

from app.db import Base
from app.db.types import ExistingEnum
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope


class RiskThresholdSet(Base):
    __tablename__ = "risk_threshold_sets"

    id = Column(String(64), primary_key=True)
    subject_type = Column(ExistingEnum(RiskSubjectType, name="risksubjecttype"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    scope = Column(ExistingEnum(RiskThresholdScope, name="riskthresholdscope"), nullable=False, default=RiskThresholdScope.GLOBAL)
    action = Column(ExistingEnum(RiskThresholdAction, name="riskthresholdaction"), nullable=False, default=RiskThresholdAction.PAYMENT)
    block_threshold = Column(Integer, nullable=False, default=90)
    review_threshold = Column(Integer, nullable=False, default=70)
    allow_threshold = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    valid_to = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_risk_threshold_sets_subject", "subject_type"),
        Index("ix_risk_threshold_sets_active", "active"),
        Index("ix_risk_threshold_sets_scope", "scope"),
        Index("ix_risk_threshold_sets_action", "action"),
    )


__all__ = ["RiskThresholdSet"]
