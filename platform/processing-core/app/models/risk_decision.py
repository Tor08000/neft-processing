from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, event
from sqlalchemy.dialects import postgresql

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.models.immutability import ImmutableRecordError
from app.models.risk_score import RiskLevel
from app.models.risk_types import RiskDecisionActor, RiskDecisionType, RiskSubjectType

JSON_TYPE = JSON().with_variant(postgresql.JSONB, "postgresql")


class RiskDecision(Base):
    __tablename__ = "risk_decisions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    decision_id = Column(String(64), nullable=False, index=True)
    subject_type = Column(ExistingEnum(RiskSubjectType, name="risksubjecttype"), nullable=False)
    subject_id = Column(String(128), nullable=False)

    score = Column(Integer, nullable=False)
    risk_level = Column(ExistingEnum(RiskLevel, name="risklevel"), nullable=False)

    threshold_set_id = Column(String(64), nullable=False)
    policy_id = Column(String(64), nullable=True)
    outcome = Column(ExistingEnum(RiskDecisionType, name="riskdecision"), nullable=False)

    model_version = Column(String(64), nullable=True)

    reasons = Column(JSON_TYPE, nullable=False, default=list)
    features_snapshot = Column(JSON_TYPE, nullable=False, default=dict)

    decided_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    decided_by = Column(ExistingEnum(RiskDecisionActor, name="riskdecisionactor"), nullable=False)

    audit_id = Column(GUID(), nullable=False)

    __table_args__ = (
        Index("ix_risk_decisions_subject", "subject_type", "subject_id"),
        Index("ix_risk_decisions_risk_level", "risk_level"),
        Index("ix_risk_decisions_outcome", "outcome"),
        Index("ix_risk_decisions_decided_at", "decided_at"),
    )


@event.listens_for(RiskDecision, "before_update")
@event.listens_for(RiskDecision, "before_delete")
def _prevent_risk_decision_mutation(mapper, connection, target: RiskDecision) -> None:
    raise ImmutableRecordError("risk_decision_immutable")


__all__ = ["RiskDecision"]
