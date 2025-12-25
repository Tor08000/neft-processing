from __future__ import annotations

from dataclasses import dataclass

from app.services.decision.context import DecisionContext


@dataclass(frozen=True)
class RiskScore:
    score: int
    model_version: str | None = None


class RiskScorer:
    def score(self, ctx: DecisionContext) -> RiskScore:  # pragma: no cover - interface
        raise NotImplementedError


class StubRiskScorer(RiskScorer):
    def __init__(self, *, default_score: int = 10) -> None:
        self.default_score = default_score

    def score(self, ctx: DecisionContext) -> RiskScore:
        score = int(ctx.metadata.get("risk_score", self.default_score))
        model_version = ctx.metadata.get("model_version")
        return RiskScore(score=score, model_version=model_version)
