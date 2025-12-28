from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, String

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.models.risk_types import RiskSubjectType


class RiskV5Label(str, Enum):
    FRAUD = "FRAUD"
    NOT_FRAUD = "NOT_FRAUD"
    UNKNOWN = "UNKNOWN"


class RiskV5LabelSource(str, Enum):
    OVERRIDE = "OVERRIDE"
    DISPUTE = "DISPUTE"
    CHARGEBACK = "CHARGEBACK"
    ANOMALY = "ANOMALY"


class RiskV5LabelRecord(Base):
    __tablename__ = "risk_v5_labels"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    decision_id = Column(String(64), nullable=False)
    subject_type = Column(ExistingEnum(RiskSubjectType, name="risksubjecttype"), nullable=False)
    subject_id = Column(String(64), nullable=False)
    label = Column(ExistingEnum(RiskV5Label, name="riskv5label"), nullable=False)
    label_source = Column(ExistingEnum(RiskV5LabelSource, name="riskv5labelsource"), nullable=False)
    confidence = Column(Integer, nullable=False)
    labeled_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_risk_v5_labels_decision", "decision_id"),
        Index("ix_risk_v5_labels_subject", "subject_type", "subject_id"),
    )


__all__ = [
    "RiskV5Label",
    "RiskV5LabelSource",
    "RiskV5LabelRecord",
]
