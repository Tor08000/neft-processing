from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.risk_score import RiskLevel, RiskScore, RiskScoreAction
from app.services.decision.context import DecisionContext
from app.services.decision.rules.scoring_rules import apply_scoring_rules, default_scoring_rules


class DecisionOutcome(str, Enum):
    ALLOW = "ALLOW"
    DECLINE = "DECLINE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True)
class DecisionResult:
    decision_id: str
    decision_version: str
    outcome: DecisionOutcome
    risk_score: int
    risk_level: RiskLevel
    explain: dict[str, object]

    def to_payload(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "decision_version": self.decision_version,
            "outcome": self.outcome.value,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "explain": self.explain,
        }


class DecisionEngine:
    def __init__(self, db: Session | None = None):
        self.db = db

    def evaluate(self, ctx: DecisionContext) -> DecisionResult:
        amount = ctx.amount if ctx.amount is not None else 0
        rules = list(ctx.scoring_rules) if ctx.scoring_rules else default_scoring_rules()
        risk_level, explanations, rule_ids = apply_scoring_rules(ctx, rules)
        if ctx.amount is not None and amount <= 0:
            risk_level = RiskLevel.HIGH
            explanations = ["invalid_amount"]
            rule_ids = []

        score = self._score_from_level(risk_level)

        risk_score = self._persist_risk_score(
            ctx=ctx,
            score=score,
            action=ctx.action,
            reason=";".join(explanations) if explanations else None,
        )
        ctx.risk_score = risk_score

        outcome = self._outcome_for_level(risk_level)
        if ctx.amount is not None and amount <= 0:
            outcome = DecisionOutcome.DECLINE

        return DecisionResult(
            decision_id=str(uuid4()),
            decision_version="1",
            outcome=outcome,
            risk_score=score,
            risk_level=risk_level,
            explain={
                "reason_codes": explanations,
                "rules_fired": rule_ids,
            },
        )

    @staticmethod
    def _score_from_level(level: RiskLevel) -> int:
        return {
            RiskLevel.LOW: 10,
            RiskLevel.MEDIUM: 50,
            RiskLevel.HIGH: 80,
            RiskLevel.VERY_HIGH: 95,
        }[level]

    @staticmethod
    def _outcome_for_level(level: RiskLevel) -> DecisionOutcome:
        if level == RiskLevel.LOW:
            return DecisionOutcome.ALLOW
        if level == RiskLevel.MEDIUM:
            return DecisionOutcome.MANUAL_REVIEW
        return DecisionOutcome.DECLINE

    def _persist_risk_score(
        self,
        *,
        ctx: DecisionContext,
        score: int,
        action: RiskScoreAction,
        reason: str | None,
    ) -> RiskScore | None:
        if self.db is None:
            return None

        record = RiskScore(
            score=score,
            actor_id=ctx.client_id,
            action=action,
            reason=reason,
        )
        self.db.add(record)
        self.db.flush()
        return record
