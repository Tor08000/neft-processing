from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.fleet_intelligence_actions import (
    FIActionCode,
    FIActionEffectLabel,
    FIActionTargetSystem,
    FAppliedActionStatus,
    FIInsightEntityType,
    FIInsightSeverity,
    FIInsightStatus,
    FIInsightType,
    FISuggestedActionStatus,
)
from app.models.unified_explain import PrimaryReason


class FleetControlInsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    insight_type: FIInsightType
    entity_type: FIInsightEntityType
    entity_id: str
    window_days: int
    severity: FIInsightSeverity
    status: FIInsightStatus
    primary_reason: PrimaryReason
    summary: str | None
    evidence: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class FleetControlSuggestedActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    insight_id: str
    action_code: FIActionCode
    target_system: FIActionTargetSystem
    payload: dict[str, Any] | None
    status: FISuggestedActionStatus
    created_at: datetime
    approved_at: datetime | None
    approved_by: str | None
    approve_reason: str | None


class FleetControlAppliedActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    insight_id: str
    action_code: FIActionCode
    applied_by: str | None
    applied_at: datetime
    reason_code: str
    reason_text: str | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    status: FAppliedActionStatus
    error_message: str | None


class FleetControlActionEffectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    applied_action_id: str
    measured_at: datetime
    window_days: int
    baseline: dict[str, Any] | None
    current: dict[str, Any] | None
    delta: dict[str, Any] | None
    effect_label: FIActionEffectLabel
    summary: str | None


class FleetControlInsightDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    insight: FleetControlInsightOut
    suggested_actions: list[FleetControlSuggestedActionOut]
    applied_actions: list[FleetControlAppliedActionOut]
    effects: list[FleetControlActionEffectOut]


class FleetControlActionDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str
    reason_text: str | None = None


__all__ = [
    "FleetControlInsightOut",
    "FleetControlSuggestedActionOut",
    "FleetControlAppliedActionOut",
    "FleetControlActionEffectOut",
    "FleetControlInsightDetailOut",
    "FleetControlActionDecisionIn",
]
