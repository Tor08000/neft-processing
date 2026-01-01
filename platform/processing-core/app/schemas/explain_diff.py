from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ExplainDiffKind = Literal["operation", "invoice", "order", "kpi"]
ExplainDiffDecision = Literal["APPROVE", "DECLINE", "REVIEW"]
ExplainDiffRiskLabel = Literal["IMPROVED", "WORSENED", "NO_CHANGE"]
ExplainDiffMemoryPenalty = Literal["LOW", "MEDIUM", "HIGH"]


class ExplainDiffContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ExplainDiffKind
    id: str


class ExplainDiffAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


class ExplainDiffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: ExplainDiffContext
    actions: list[ExplainDiffAction] = Field(..., min_length=1, max_length=3)


class ExplainDiffReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    title: str
    weight: float | None = None


class ExplainDiffEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    type: str | None = None
    source: str | None = None
    confidence: float | None = None


class ExplainDiffSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_score: float | None = None
    decision: ExplainDiffDecision | None = None
    reasons: list[ExplainDiffReason] = Field(default_factory=list)
    evidence: list[ExplainDiffEvidence] = Field(default_factory=list)


class ExplainDiffReasonDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    delta: float


class ExplainDiffReasons(BaseModel):
    model_config = ConfigDict(extra="forbid")

    removed: list[str] = Field(default_factory=list)
    weakened: list[ExplainDiffReasonDelta] = Field(default_factory=list)
    strengthened: list[ExplainDiffReasonDelta] = Field(default_factory=list)
    added: list[str] = Field(default_factory=list)


class ExplainDiffEvidenceChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    removed: list[str] = Field(default_factory=list)
    added: list[str] = Field(default_factory=list)


class ExplainDiffRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delta: float
    label: ExplainDiffRiskLabel


class ExplainDiffMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation: bool = True
    confidence: float | None = None
    memory_penalty: ExplainDiffMemoryPenalty | None = None


class ExplainDiffPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk: ExplainDiffRisk
    reasons: ExplainDiffReasons
    evidence: ExplainDiffEvidenceChanges


class ExplainDiffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    before: ExplainDiffSnapshot
    after: ExplainDiffSnapshot
    diff: ExplainDiffPayload
    meta: ExplainDiffMeta


__all__ = [
    "ExplainDiffAction",
    "ExplainDiffContext",
    "ExplainDiffRequest",
    "ExplainDiffResponse",
]
