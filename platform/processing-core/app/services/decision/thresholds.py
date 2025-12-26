from __future__ import annotations

from dataclasses import dataclass

from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskDecisionType, RiskOutcome


@dataclass(frozen=True)
class ThresholdEvaluation:
    outcome: RiskOutcome
    decision: RiskDecisionType
    thresholds: dict[str, int]


def evaluate_thresholds(score: int, threshold_set: RiskThresholdSet) -> ThresholdEvaluation:
    thresholds = {
        "block": int(threshold_set.block_threshold),
        "review": int(threshold_set.review_threshold),
        "allow": int(threshold_set.allow_threshold),
    }
    if score >= thresholds["block"]:
        outcome = RiskOutcome.BLOCK
        decision = RiskDecisionType.BLOCK
    elif score >= thresholds["review"]:
        outcome = RiskOutcome.REVIEW_REQUIRED
        decision = RiskDecisionType.ALLOW_WITH_REVIEW
    elif score >= thresholds["allow"]:
        outcome = RiskOutcome.ALLOW
        decision = RiskDecisionType.ALLOW
    else:
        outcome = RiskOutcome.ALLOW_WITH_LOG
        decision = RiskDecisionType.ALLOW
    return ThresholdEvaluation(outcome=outcome, decision=decision, thresholds=thresholds)


__all__ = ["ThresholdEvaluation", "evaluate_thresholds"]
