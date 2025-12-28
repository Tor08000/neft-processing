from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, JSON
from sqlalchemy.dialects import postgresql

from app.db import Base
from app.db.types import GUID, new_uuid_str

JSON_TYPE = JSON().with_variant(postgresql.JSONB, "postgresql")


class DecisionResult(Base):
    __tablename__ = "decision_results"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    decision_id = Column(String(64), nullable=False, unique=True, index=True)
    decision_version = Column(String(32), nullable=False)
    action = Column(String(64), nullable=False, index=True)
    outcome = Column(String(32), nullable=False, index=True)
    risk_score = Column(Integer, nullable=True)
    rule_hits = Column(JSON_TYPE, nullable=False, default=list)
    model_version = Column(String(64), nullable=True)
    context_hash = Column(String(64), nullable=False, index=True)
    explain = Column(JSON_TYPE, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        {
            "comment": "Deterministic decision results for audit and dispute resolution.",
        },
    )


__all__ = ["DecisionResult"]
