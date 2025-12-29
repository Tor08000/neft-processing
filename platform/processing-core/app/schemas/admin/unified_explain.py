from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.unified_explain import PrimaryReason
from app.services.explain.actions import ActionItem
from app.services.explain.escalation import EscalationInfo
from app.services.explain.sla import SLAClock


class FleetAssistantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_insight: str
    action: ActionItem | None = None
    action_effect_pct: int | None = None
    confidence: int
    sla: SLAClock | None = None
    escalation: EscalationInfo | None = None
    answers: dict[str, str]
    projection: FleetAssistantProjection | None = None
    benchmark: FleetAssistantBenchmark | None = None


class FleetAssistantProjectionKPI(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpi: str
    direction: str
    estimate: str


class FleetAssistantProjectionAppliedBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float
    sample_size: int
    half_life_days: int
    trend_label: str


class FleetAssistantProjectionApplied(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probability_improved_pct: int
    expected_effect_label: str
    expected_time_window_days: int
    expected_kpis: list[FleetAssistantProjectionKPI]
    basis: FleetAssistantProjectionAppliedBasis
    warnings: list[str] = Field(default_factory=list)


class FleetAssistantProjectionEscalationRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    likely: bool
    eta_minutes: int | None = None
    reason: str


class FleetAssistantProjectionIgnoredBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trend_label: str
    aging_days: int | None = None
    sla_remaining_minutes: int | None = None


class FleetAssistantProjectionIgnored(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probability_worse_pct: int
    expected_effect_label: str
    escalation_risk: FleetAssistantProjectionEscalationRisk
    expected_kpis: list[FleetAssistantProjectionKPI]
    basis: FleetAssistantProjectionIgnoredBasis


class FleetAssistantProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    if_applied: FleetAssistantProjectionApplied
    if_ignored: FleetAssistantProjectionIgnored


class FleetAssistantBenchmarkPeerGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str
    client_id: str | None = None
    tenant_id: int | None = None
    network_id: str | None = None


class FleetAssistantBenchmarkPercentile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    value: float | None = None
    percentile: float | None = None
    label: str | None = None
    p50: float | None = None
    p80: float | None = None
    p90: float | None = None


class FleetAssistantBenchmarkHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trend_label: str | None = None
    delta_7d: float | None = None


class FleetAssistantBenchmarkBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str
    window_days: int
    n: int
    entity_type: str | None = None
    as_of: str | None = None


class FleetAssistantBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    peer_group: FleetAssistantBenchmarkPeerGroup
    percentiles: list[FleetAssistantBenchmarkPercentile]
    n: int
    basis: FleetAssistantBenchmarkBasis
    history: FleetAssistantBenchmarkHistory | None = None


class UnifiedExplainView(str, Enum):
    FLEET = "FLEET"
    ACCOUNTANT = "ACCOUNTANT"
    FULL = "FULL"


class UnifiedExplainSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    id: str
    ts: str | None = None
    client_id: str | None = None
    vehicle_id: str | None = None
    driver_id: str | None = None


class UnifiedExplainResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    primary_reason: PrimaryReason = PrimaryReason.UNKNOWN
    secondary_reasons: list[PrimaryReason] = Field(default_factory=list)
    decline_code: str | None = None


class UnifiedExplainIds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_decision_id: str | None = None
    ledger_transaction_id: str | None = None
    invoice_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    money_flow_event_ids: list[str] = Field(default_factory=list)
    snapshot_id: str | None = None
    snapshot_hash: str | None = None


class UnifiedExplainResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_reason: PrimaryReason
    secondary_reasons: list[PrimaryReason] = Field(default_factory=list)
    subject: UnifiedExplainSubject
    result: UnifiedExplainResult
    sections: dict[str, Any]
    ids: UnifiedExplainIds
    recommendations: list[str]
    actions: list[ActionItem] = Field(default_factory=list)
    sla: SLAClock | None = None
    escalation: EscalationInfo | None = None
    assistant: FleetAssistantResponse | None = None


__all__ = [
    "UnifiedExplainIds",
    "UnifiedExplainResponse",
    "UnifiedExplainResult",
    "UnifiedExplainSubject",
    "UnifiedExplainView",
    "FleetAssistantResponse",
    "FleetAssistantProjection",
    "FleetAssistantProjectionApplied",
    "FleetAssistantProjectionAppliedBasis",
    "FleetAssistantProjectionEscalationRisk",
    "FleetAssistantProjectionIgnored",
    "FleetAssistantProjectionIgnoredBasis",
    "FleetAssistantProjectionKPI",
    "FleetAssistantBenchmark",
    "FleetAssistantBenchmarkBasis",
    "FleetAssistantBenchmarkHistory",
    "FleetAssistantBenchmarkPeerGroup",
    "FleetAssistantBenchmarkPercentile",
    "ActionItem",
    "EscalationInfo",
    "SLAClock",
]
