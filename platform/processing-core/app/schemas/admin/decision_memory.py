from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.decision_memory import DecisionMemoryEffectLabel, DecisionMemoryEntityType


class DecisionOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: int
    client_id: str | None
    entity_type: DecisionMemoryEntityType
    entity_id: str
    insight_id: str | None
    applied_action_id: str | None
    action_code: str
    bundle_code: str | None
    applied_at: datetime
    measured_at: datetime | None
    window_days: int
    effect_label: DecisionMemoryEffectLabel
    effect_delta: dict[str, Any] | None
    confidence_at_apply: float | None
    context: dict[str, Any] | None
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


class DecisionCooldownOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_code: str
    entity_type: DecisionMemoryEntityType
    entity_id: str
    cooldown: bool
    reason: str | None
    recent_count: int
    failed_streak: int


__all__ = ["DecisionActionStatsOut", "DecisionCooldownOut", "DecisionOutcomeOut"]
