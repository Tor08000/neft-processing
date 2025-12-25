from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class RiskScoreAction(str, Enum):
    PAYMENT = "PAYMENT"
    INVOICE = "INVOICE"
    PAYOUT = "PAYOUT"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    score = Column(Integer, nullable=False)
    actor_id = Column(String(128), nullable=False)
    action = Column(ExistingEnum(RiskScoreAction, name="risk_score_action"), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_risk_score_actor", "actor_id"),
        Index("ix_risk_score_action", "action"),
    )


__all__ = ["RiskLevel", "RiskScore", "RiskScoreAction"]
