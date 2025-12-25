from __future__ import annotations

from datetime import datetime

from app.services.decision.context import DecisionContext


def build_explain(
    ctx: DecisionContext,
    *,
    matched_rules: list[str],
    rule_explanations: dict[str, str],
    thresholds: dict[str, int],
    risk_score: int | None,
    model_version: str | None,
    evaluated_at: datetime,
) -> dict:
    return {
        "matched_rules": matched_rules,
        "rule_explanations": rule_explanations,
        "thresholds": thresholds,
        "inputs": ctx.to_payload(),
        "scoring": {
            "score": risk_score,
            "model_version": model_version,
        },
        "timestamps": {
            "evaluated_at": evaluated_at.isoformat(),
        },
    }
