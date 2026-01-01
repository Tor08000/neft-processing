from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


ExplainDiffKind = Literal["operation", "invoice", "order", "kpi"]
ExplainDiffDecision = Literal["APPROVE", "DECLINE", "REVIEW"]
ExplainDiffReasonStatus = Literal["added", "removed", "strengthened", "weakened", "unchanged"]
ExplainDiffEvidenceStatus = Literal["added", "removed", "changed"]


class ExplainDiffSnapshotLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    label: str


class ExplainDiffMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ExplainDiffKind
    entity_id: str | None = None
    left: ExplainDiffSnapshotLabel
    right: ExplainDiffSnapshotLabel


class ExplainDiffScoreDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_before: float | None = None
    risk_after: float | None = None
    delta: float | None = None


class ExplainDiffDecisionDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    before: ExplainDiffDecision | None = None
    after: ExplainDiffDecision | None = None


class ExplainDiffReasonItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str
    weight_before: float | None = None
    weight_after: float | None = None
    delta: float
    status: ExplainDiffReasonStatus


class ExplainDiffEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    status: ExplainDiffEvidenceStatus


class ExplainDiffActionImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    expected_delta: float
    confidence: float


class ExplainDiffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: ExplainDiffMeta
    score_diff: ExplainDiffScoreDiff
    decision_diff: ExplainDiffDecisionDiff
    reasons_diff: list[ExplainDiffReasonItem]
    evidence_diff: list[ExplainDiffEvidenceItem]
    action_impact: ExplainDiffActionImpact | None = None


__all__ = [
    "ExplainDiffActionImpact",
    "ExplainDiffDecision",
    "ExplainDiffEvidenceItem",
    "ExplainDiffKind",
    "ExplainDiffMeta",
    "ExplainDiffReasonItem",
    "ExplainDiffResponse",
    "ExplainDiffScoreDiff",
]
