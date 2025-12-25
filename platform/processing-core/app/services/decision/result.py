from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.models.risk_score import RiskLevel
from app.models.risk_types import RiskDecisionType


class DecisionOutcome(str, Enum):
    ALLOW = "ALLOW"
    DECLINE = "DECLINE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True)
class DecisionResult:
    decision_id: str
    decision_version: str
    outcome: DecisionOutcome
    risk_score: int | None
    risk_level: RiskLevel | None = None
    rule_hits: list[str] = field(default_factory=list)
    model_version: str | None = None
    explain: dict = field(default_factory=dict)
    risk_decision: RiskDecisionType | None = None
    threshold_set_id: str | None = None
    policy_id: str | None = None

    def to_payload(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "decision_version": self.decision_version,
            "outcome": self.outcome.value if hasattr(self.outcome, "value") else self.outcome,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "rule_hits": list(self.rule_hits),
            "model_version": self.model_version,
            "explain": self.explain,
            "risk_decision": self.risk_decision.value if self.risk_decision else None,
            "threshold_set_id": self.threshold_set_id,
            "policy_id": self.policy_id,
        }
