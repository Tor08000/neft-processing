from __future__ import annotations

from dataclasses import dataclass

from app.services.decision.context import DecisionContext


@dataclass(frozen=True)
class RiskScore:
    score: int
    model_version: str | None = None
    source: str = "stub_default"
    assumptions: tuple[str, ...] = ()
    evidence: dict | None = None


class RiskScorer:
    def score(self, ctx: DecisionContext) -> RiskScore:  # pragma: no cover - interface
        raise NotImplementedError


class StubRiskScorer(RiskScorer):
    def __init__(self, *, default_score: int = 10) -> None:
        self.default_score = default_score

    def score(self, ctx: DecisionContext) -> RiskScore:
        assumptions: list[str] = []
        evidence = {"metadata_keys": sorted(ctx.metadata.keys())}
        if "risk_score" in ctx.metadata:
            score = int(ctx.metadata["risk_score"])
            source = str(ctx.metadata.get("risk_score_source") or "context_metadata")
            raw_assumptions = ctx.metadata.get("risk_score_assumptions") or []
            if isinstance(raw_assumptions, list):
                assumptions.extend(str(item) for item in raw_assumptions if item)
            evidence["score_input"] = "context_metadata"
        else:
            score = self.default_score
            source = "stub_default"
            assumptions.extend(["stub_score_default", "scorer_not_configured"])
            evidence.update(
                {
                    "compatibility_tail": "decision_engine_default_scorer",
                    "default_score": self.default_score,
                    "not_ml": True,
                }
            )
        model_version = ctx.metadata.get("model_version")
        return RiskScore(
            score=score,
            model_version=model_version,
            source=source,
            assumptions=tuple(assumptions),
            evidence=evidence,
        )
