from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class DecisionMemoryEntityType(str, Enum):
    DRIVER = "DRIVER"
    VEHICLE = "VEHICLE"
    STATION = "STATION"
    CLIENT = "CLIENT"


class DecisionMemoryEffectLabel(str, Enum):
    IMPROVED = "IMPROVED"
    NO_CHANGE = "NO_CHANGE"
    WORSE = "WORSE"
    UNKNOWN = "UNKNOWN"


class DecisionOutcome(Base):
    __tablename__ = "decision_outcomes"
    __table_args__ = (
        UniqueConstraint("applied_action_id", name="uq_decision_outcomes_applied_action"),
        Index("ix_decision_outcomes_tenant", "tenant_id"),
        Index("ix_decision_outcomes_entity", "entity_type", "entity_id"),
        Index("ix_decision_outcomes_action", "action_code"),
        Index("ix_decision_outcomes_applied_at", "applied_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=True, index=True)
    entity_type = Column(ExistingEnum(DecisionMemoryEntityType, name="decision_memory_entity_type"), nullable=False)
    entity_id = Column(String(64), nullable=False)
    insight_id = Column(GUID(), nullable=True, index=True)
    applied_action_id = Column(GUID(), nullable=True, index=True)
    action_code = Column(String(128), nullable=False)
    bundle_code = Column(String(64), nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=False)
    measured_at = Column(DateTime(timezone=True), nullable=True, index=True)
    window_days = Column(Integer, nullable=False)
    effect_label = Column(ExistingEnum(DecisionMemoryEffectLabel, name="decision_memory_effect_label"), nullable=False)
    effect_delta = Column(JSON, nullable=True)
    confidence_at_apply = Column(Float, nullable=True)
    context = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DecisionMemoryRecord(Base):
    __tablename__ = "decision_memory"
    __table_args__ = (
        Index("ix_decision_memory_case_at", "case_id", "decision_at"),
        Index("ix_decision_memory_audit_event", "audit_event_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    case_id = Column(GUID(), nullable=True, index=True)
    decision_type = Column(String(32), nullable=False)
    decision_ref_id = Column(GUID(), nullable=False)
    decision_at = Column(DateTime(timezone=True), nullable=False)
    decided_by_user_id = Column(GUID(), nullable=True)
    context_snapshot = Column(JSON, nullable=False)
    rationale = Column(Text, nullable=True)
    score_snapshot = Column(JSON, nullable=True)
    mastery_snapshot = Column(JSON, nullable=True)
    audit_event_id = Column(GUID(), ForeignKey("case_events.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DecisionActionStatsDaily(Base):
    __tablename__ = "decision_action_stats_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "action_code",
            "entity_type",
            "day",
            "client_id",
            name="uq_decision_action_stats_daily_scope",
        ),
        Index("ix_decision_action_stats_daily_tenant", "tenant_id"),
        Index("ix_decision_action_stats_daily_action", "action_code"),
        Index("ix_decision_action_stats_daily_entity", "entity_type"),
        Index("ix_decision_action_stats_daily_day", "day"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=True, index=True)
    action_code = Column(String(128), nullable=False)
    entity_type = Column(ExistingEnum(DecisionMemoryEntityType, name="decision_memory_entity_type"), nullable=False)
    day = Column(Date, nullable=False)
    applied_count = Column(Integer, nullable=False, default=0, server_default="0")
    improved_count = Column(Integer, nullable=False, default=0, server_default="0")
    no_change_count = Column(Integer, nullable=False, default=0, server_default="0")
    worse_count = Column(Integer, nullable=False, default=0, server_default="0")
    weighted_success = Column(Float, nullable=False, default=0.0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "DecisionMemoryEntityType",
    "DecisionMemoryEffectLabel",
    "DecisionMemoryRecord",
    "DecisionOutcome",
    "DecisionActionStatsDaily",
]
