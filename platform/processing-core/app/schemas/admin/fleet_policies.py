from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.fuel import (
    FleetActionBreachKind,
    FleetActionPolicyAction,
    FleetActionPolicyScopeType,
    FleetActionTriggerType,
    FleetPolicyExecutionStatus,
    FleetNotificationSeverity,
)


class AdminFleetActionPolicyOut(BaseModel):
    id: str
    client_id: str
    scope_type: FleetActionPolicyScopeType
    scope_id: str | None = None
    trigger_type: FleetActionTriggerType
    trigger_severity_min: FleetNotificationSeverity
    breach_kind: FleetActionBreachKind | None = None
    action: FleetActionPolicyAction
    cooldown_seconds: int
    active: bool
    created_at: datetime


class AdminFleetActionPolicyListResponse(BaseModel):
    items: list[AdminFleetActionPolicyOut]


class AdminFleetPolicyExecutionOut(BaseModel):
    id: str
    client_id: str
    policy_id: str
    event_type: str
    event_id: str
    action: str
    status: FleetPolicyExecutionStatus
    reason: str | None = None
    created_at: datetime


class AdminFleetPolicyExecutionListResponse(BaseModel):
    items: list[AdminFleetPolicyExecutionOut]


class AdminFleetCardUnblockIn(BaseModel):
    reason: str
