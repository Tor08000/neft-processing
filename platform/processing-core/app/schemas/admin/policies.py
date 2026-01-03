from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class PolicyType(str, Enum):
    FLEET = "fleet"
    FINANCE = "finance"
    MARKETPLACE = "marketplace"


class PolicyStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class PolicyScope(BaseModel):
    tenant_id: int | None = None
    client_id: str | None = None


class PolicyExplainRef(BaseModel):
    kind: str
    id: str
    type: PolicyType


class AdminPolicyIndexItem(BaseModel):
    id: str
    type: PolicyType
    title: str
    status: PolicyStatus
    scope: PolicyScope
    actions: list[str]
    explain_ref: PolicyExplainRef
    updated_at: datetime | None = None
    toggle_supported: bool = False


class AdminPolicyIndexResponse(BaseModel):
    items: list[AdminPolicyIndexItem]
    total: int
    limit: int
    offset: int


class AdminPolicyHeader(BaseModel):
    id: str
    type: PolicyType
    title: str
    status: PolicyStatus
    scope: PolicyScope
    actions: list[str]
    updated_at: datetime | None = None
    toggle_supported: bool = False


class AdminPolicyDetailResponse(BaseModel):
    header: AdminPolicyHeader
    policy: dict[str, Any] | None
    explain: dict[str, Any] | None = None


class AdminPolicyExecutionOut(BaseModel):
    id: str
    policy_id: str
    event_type: str
    event_id: str
    action: str
    status: str
    reason: str | None = None
    created_at: datetime


class AdminPolicyExecutionListResponse(BaseModel):
    items: list[AdminPolicyExecutionOut]

