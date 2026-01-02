from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.decision_memory import DecisionMemoryEffectLabel, DecisionMemoryEntityType


class DecisionOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: int
    client_id: str | None = None
    entity_type: DecisionMemoryEntityType
    entity_id: str
    insight_id: str | None = None
    applied_action_id: str | None = None
    action_code: str
    bundle_code: str | None = None
    applied_at: datetime
    measured_at: datetime | None = None
    window_days: int
    effect_label: DecisionMemoryEffectLabel
    effect_delta: dict[str, Any] | None = None
    confidence_at_apply: float | None = None
    context: dict[str, Any] | None = None
    created_at: datetime


class DecisionActionStatsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_code: str
    entity_type: DecisionMemoryEntityType
    window_days: int
    applied_count: int
    improved_count: int
    no_change_count: int
    worse_count: int
    success_rate: float
    weighted_success_rate: float
    weighted_success: float
    weighted_applied: float


class DecisionCooldownOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_code: str
    entity_type: DecisionMemoryEntityType
    entity_id: str
    cooldown: bool
    reason: str | None = None
    recent_count: int
    failed_streak: int


class DecisionMemoryEntryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    case_id: str | None = None
    decision_type: str
    decision_ref_id: str
    decision_at: datetime
    decided_by_user_id: str | None = None
    context_snapshot: dict[str, Any]
    rationale: str | None = None
    score_snapshot: dict[str, Any] | None = None
    mastery_snapshot: dict[str, Any] | None = None
    audit_event_id: str
    created_at: datetime
    audit_chain_verified: bool
    audit_signature_verified: bool
    artifact_signature_verified: bool | None = None


class DecisionMemoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DecisionMemoryEntryOut]
    next_cursor: str | None = None


__all__ = [
    "DecisionActionStatsOut",
    "DecisionCooldownOut",
    "DecisionMemoryEntryOut",
    "DecisionMemoryListResponse",
    "DecisionOutcomeOut",
]
