from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ExplainKind = Literal["operation", "invoice", "marketplace_order", "kpi"]
ExplainDecision = Literal["APPROVE", "DECLINE", "REVIEW"]
ExplainScoreBand = Literal["low", "medium", "high", "block", "review"]
ExplainEvidenceType = Literal["metric", "field", "rule", "document", "event"]
ExplainEffect = Literal["risk_down", "risk_up", "risk_neutral"]
ExplainPriority = Literal["low", "medium", "high"]


class ExplainReasonNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    weight: float = Field(..., ge=0, le=1)
    children: list["ExplainReasonNode"] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class ExplainEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: ExplainEvidenceType
    label: str
    value: dict[str, Any] | list[Any] | str | int | float | None = None
    source: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ExplainDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    kind: str
    url: str


class ExplainRecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_code: str
    title: str
    description: str | None = None
    expected_effect: ExplainEffect | None = None
    priority: ExplainPriority | None = None


class ExplainActionCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_code: str
    label: str
    description: str | None = None
    risk_hint: str | None = None
    side_effects: str | None = None


class ExplainV2Response(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ExplainKind
    id: str
    decision: ExplainDecision
    score: int | None = Field(default=None, ge=0, le=100)
    score_band: ExplainScoreBand | None = None
    policy_snapshot: str | None = None
    generated_at: datetime
    reason_tree: ExplainReasonNode | None = None
    evidence: list[ExplainEvidence] = Field(default_factory=list)
    documents: list[ExplainDocument] = Field(default_factory=list)
    recommended_actions: list[ExplainRecommendedAction] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ensure_root_weight(self) -> "ExplainV2Response":
        if self.reason_tree and self.reason_tree.weight != 1.0:
            raise ValueError("root_reason_weight_must_be_1.0")
        return self


ExplainReasonNode.model_rebuild()

__all__ = [
    "ExplainActionCatalogItem",
    "ExplainDecision",
    "ExplainDocument",
    "ExplainEvidence",
    "ExplainEvidenceType",
    "ExplainKind",
    "ExplainReasonNode",
    "ExplainRecommendedAction",
    "ExplainV2Response",
]
