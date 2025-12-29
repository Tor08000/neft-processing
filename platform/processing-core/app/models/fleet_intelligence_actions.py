from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.models.unified_explain import PrimaryReason


class FIInsightType(str, Enum):
    DRIVER_BEHAVIOR_DEGRADING = "DRIVER_BEHAVIOR_DEGRADING"
    STATION_TRUST_DEGRADING = "STATION_TRUST_DEGRADING"
    VEHICLE_EFFICIENCY_DEGRADING = "VEHICLE_EFFICIENCY_DEGRADING"


class FIInsightEntityType(str, Enum):
    DRIVER = "DRIVER"
    VEHICLE = "VEHICLE"
    STATION = "STATION"


class FIInsightSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FIInsightStatus(str, Enum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    ACTION_PLANNED = "ACTION_PLANNED"
    ACTION_APPLIED = "ACTION_APPLIED"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class FIActionCode(str, Enum):
    SUGGEST_LIMIT_PROFILE_SAFE = "SUGGEST_LIMIT_PROFILE_SAFE"
    SUGGEST_RESTRICT_NIGHT_FUELING = "SUGGEST_RESTRICT_NIGHT_FUELING"
    SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL = "SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL"
    SUGGEST_EXCLUDE_STATION_FROM_ROUTES = "SUGGEST_EXCLUDE_STATION_FROM_ROUTES"
    SUGGEST_VEHICLE_DIAGNOSTIC = "SUGGEST_VEHICLE_DIAGNOSTIC"


class FIActionTargetSystem(str, Enum):
    CRM = "CRM"
    LOGISTICS = "LOGISTICS"
    OPS = "OPS"


class FISuggestedActionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"


class FAppliedActionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class FIActionEffectLabel(str, Enum):
    IMPROVED = "IMPROVED"
    NO_CHANGE = "NO_CHANGE"
    WORSE = "WORSE"


class FIInsight(Base):
    __tablename__ = "fi_insights"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "insight_type",
            "entity_type",
            "entity_id",
            "window_days",
            "created_at",
            name="uq_fi_insight_scope_created",
        ),
        Index("ix_fi_insights_client_status", "client_id", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    insight_type = Column(ExistingEnum(FIInsightType, name="fi_insight_type"), nullable=False)
    entity_type = Column(ExistingEnum(FIInsightEntityType, name="fi_insight_entity_type"), nullable=False)
    entity_id = Column(GUID(), nullable=False, index=True)
    window_days = Column(Integer, nullable=False)
    severity = Column(ExistingEnum(FIInsightSeverity, name="fi_insight_severity"), nullable=False)
    status = Column(ExistingEnum(FIInsightStatus, name="fi_insight_status"), nullable=False)
    primary_reason = Column(ExistingEnum(PrimaryReason, name="ops_escalation_primary_reason"), nullable=False)
    summary = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    acked_at = Column(DateTime(timezone=True), nullable=True)
    acked_by = Column(String(64), nullable=True)
    ack_reason = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(64), nullable=True)
    resolve_reason = Column(Text, nullable=True)


class FISuggestedAction(Base):
    __tablename__ = "fi_suggested_actions"
    __table_args__ = (
        UniqueConstraint("insight_id", "action_code", name="uq_fi_suggested_action_code"),
        Index("ix_fi_suggested_actions_status", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    insight_id = Column(GUID(), ForeignKey("fi_insights.id"), nullable=False, index=True)
    action_code = Column(ExistingEnum(FIActionCode, name="fi_action_code"), nullable=False)
    target_system = Column(ExistingEnum(FIActionTargetSystem, name="fi_action_target_system"), nullable=False)
    payload = Column(JSON, nullable=True)
    status = Column(ExistingEnum(FISuggestedActionStatus, name="fi_suggested_action_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String(64), nullable=True)
    approve_reason = Column(Text, nullable=True)


class FIAppliedAction(Base):
    __tablename__ = "fi_applied_actions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    insight_id = Column(GUID(), ForeignKey("fi_insights.id"), nullable=False, index=True)
    action_code = Column(ExistingEnum(FIActionCode, name="fi_action_code"), nullable=False)
    applied_by = Column(String(64), nullable=True)
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reason_code = Column(String(64), nullable=False)
    reason_text = Column(Text, nullable=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    status = Column(ExistingEnum(FAppliedActionStatus, name="fi_applied_action_status"), nullable=False)
    error_message = Column(Text, nullable=True)


class FIActionEffect(Base):
    __tablename__ = "fi_action_effects"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    applied_action_id = Column(GUID(), ForeignKey("fi_applied_actions.id"), nullable=False, index=True)
    measured_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    window_days = Column(Integer, nullable=False)
    baseline = Column(JSON, nullable=True)
    current = Column(JSON, nullable=True)
    delta = Column(JSON, nullable=True)
    effect_label = Column(ExistingEnum(FIActionEffectLabel, name="fi_action_effect_label"), nullable=False)
    summary = Column(Text, nullable=True)


__all__ = [
    "FIInsightType",
    "FIInsightEntityType",
    "FIInsightSeverity",
    "FIInsightStatus",
    "FIActionCode",
    "FIActionTargetSystem",
    "FISuggestedActionStatus",
    "FAppliedActionStatus",
    "FIActionEffectLabel",
    "FIInsight",
    "FISuggestedAction",
    "FIAppliedAction",
    "FIActionEffect",
]
