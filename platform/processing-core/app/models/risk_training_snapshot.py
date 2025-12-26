from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, event
from sqlalchemy.dialects import postgresql

from app.db import Base
from app.db.types import GUID, new_uuid_str
from app.models.immutability import ImmutableRecordError

JSON_TYPE = JSON().with_variant(postgresql.JSONB, "postgresql")


class RiskTrainingSnapshot(Base):
    __tablename__ = "risk_training_snapshots"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    decision_id = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    score = Column(Integer, nullable=False)
    outcome = Column(String(32), nullable=False)
    model_version = Column(String(64), nullable=True)
    features_version = Column(String(32), nullable=False, default="v1")
    features_hash = Column(String(64), nullable=False)
    context = Column(JSON_TYPE, nullable=False)
    policy = Column(JSON_TYPE, nullable=True)
    thresholds = Column(JSON_TYPE, nullable=False)
    features = Column(JSON_TYPE, nullable=False)
    post_factum_outcome = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_risk_training_snapshots_decision", "decision_id"),
        Index("ix_risk_training_snapshots_created", "created_at"),
    )


@event.listens_for(RiskTrainingSnapshot, "before_update")
@event.listens_for(RiskTrainingSnapshot, "before_delete")
def _prevent_risk_training_snapshot_mutation(mapper, connection, target: RiskTrainingSnapshot) -> None:
    raise ImmutableRecordError("risk_training_snapshot_immutable")


__all__ = ["RiskTrainingSnapshot"]
