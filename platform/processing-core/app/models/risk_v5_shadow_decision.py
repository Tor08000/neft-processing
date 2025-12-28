from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, event
from sqlalchemy.dialects import postgresql

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.models.immutability import ImmutableRecordError
from app.models.risk_types import RiskDecisionType, RiskSubjectType

JSON_TYPE = JSON().with_variant(postgresql.JSONB, "postgresql")


class RiskV5ShadowDecision(Base):
    __tablename__ = "risk_v5_shadow_decisions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    decision_id = Column(String(64), nullable=False)
    tenant_id = Column(Integer, nullable=True)
    client_id = Column(String(64), nullable=True)
    subject_type = Column(ExistingEnum(RiskSubjectType, name="risksubjecttype"), nullable=False)
    subject_id = Column(String(64), nullable=False)
    v4_score = Column(Integer, nullable=True)
    v4_outcome = Column(ExistingEnum(RiskDecisionType, name="riskdecision"), nullable=False)
    v4_policy_id = Column(String(64), nullable=True)
    v4_threshold_set_id = Column(String(64), nullable=True)
    v5_score = Column(Integer, nullable=True)
    v5_predicted_outcome = Column(String(32), nullable=True)
    v5_model_version = Column(String(64), nullable=True)
    v5_selector = Column(String(64), nullable=True)
    features_schema_version = Column(String(32), nullable=False)
    features_hash = Column(String(64), nullable=False)
    features_snapshot = Column(JSON_TYPE, nullable=False)
    explain = Column(JSON_TYPE, nullable=True)
    error = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_risk_v5_shadow_decisions_decision", "decision_id"),
        Index("ix_risk_v5_shadow_decisions_subject", "subject_type"),
        Index("ix_risk_v5_shadow_decisions_created", "created_at"),
    )


@event.listens_for(RiskV5ShadowDecision, "before_update")
@event.listens_for(RiskV5ShadowDecision, "before_delete")
def _prevent_risk_v5_shadow_decision_mutation(mapper, connection, target: RiskV5ShadowDecision) -> None:
    raise ImmutableRecordError("risk_v5_shadow_decision_immutable")


__all__ = ["RiskV5ShadowDecision"]
