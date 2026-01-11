from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.unified_rule import UnifiedRulePolicy, UnifiedRuleScope


class RuleWindowConfig(BaseModel):
    type: Literal["rolling", "calendar"]
    unit: Literal["minute", "hour", "day", "month"]
    size: int = Field(ge=1)
    timezone: str | None = None
    anchor: str | None = None


class RuleValueConfig(BaseModel):
    op: str
    threshold: float | int | None = None
    currency: str | None = None
    precision: int | None = None
    burst: int | None = None
    soft_threshold: float | int | None = None


class RuleEvaluationSubject(BaseModel):
    client_id: str | None = None
    partner_id: str | None = None
    user_id: str | None = None


class RuleEvaluationObject(BaseModel):
    card_id: str | None = None
    vehicle_id: str | None = None
    endpoint: str | None = None
    ip: str | None = None
    country: str | None = None
    amount: float | int | None = None
    currency: str | None = None
    method: str | None = None
    document_id: str | None = None


class RuleEvaluationContext(BaseModel):
    timestamp: datetime
    scope: UnifiedRuleScope
    subject: RuleEvaluationSubject = Field(default_factory=RuleEvaluationSubject)
    object: RuleEvaluationObject = Field(default_factory=RuleEvaluationObject)


class SandboxSyntheticRequest(BaseModel):
    mode: Literal["synthetic"]
    at: datetime
    scope: UnifiedRuleScope
    context: dict[str, Any]
    synthetic_metrics: dict[str, float | int] = Field(default_factory=dict)
    version_id: int | None = None


class SandboxHistoricalRequest(BaseModel):
    mode: Literal["historical"]
    scope: UnifiedRuleScope
    transaction_id: str
    version_id: int | None = None


SandboxRequest = SandboxSyntheticRequest | SandboxHistoricalRequest


class SandboxMatchedRule(BaseModel):
    code: str
    policy: UnifiedRulePolicy
    priority: int
    reason_code: str | None = None
    explain: str | None = None


class SandboxVersionInfo(BaseModel):
    rule_set_version_id: int
    scope: UnifiedRuleScope


class SandboxExplain(BaseModel):
    inputs: dict[str, Any]
    metrics: dict[str, Any]
    resolution: dict[str, Any]


class SandboxResponse(BaseModel):
    version: SandboxVersionInfo | None
    matched_rules: list[SandboxMatchedRule]
    decision: UnifiedRulePolicy
    reason_codes: list[str]
    explain: SandboxExplain


class RuleSetVersionCreate(BaseModel):
    name: str
    scope: UnifiedRuleScope
    notes: str | None = None
    parent_version_id: int | None = None


class RuleSetVersionOut(BaseModel):
    id: int
    name: str
    scope: UnifiedRuleScope
    status: str
    created_at: datetime
    published_at: datetime | None
    activated_at: datetime | None
    created_by: str | None = None
    notes: str | None = None
    parent_version_id: int | None = None


class UnifiedRuleCreate(BaseModel):
    code: str
    scope: UnifiedRuleScope
    selector: dict[str, Any] | None = None
    window: dict[str, Any] | None = None
    metric: str | None = None
    value: dict[str, Any] | None = None
    policy: str
    priority: int = 100
    reason_code: str | None = None
    explain_template: str | None = None
    tags: list[str] | None = None


class UnifiedRuleOut(BaseModel):
    id: int
    code: str
    scope: UnifiedRuleScope
    selector: dict[str, Any] | None
    window: dict[str, Any] | None
    metric: str | None
    value: dict[str, Any] | None
    policy: str
    priority: int
    reason_code: str | None
    explain_template: str | None
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime
