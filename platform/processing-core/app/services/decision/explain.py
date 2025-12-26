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
    decision: str | None,
    model_version: str | None,
    model_name: str | None,
    policy_label: str | None,
    factors: list[str],
    evaluated_at: datetime,
    policy: dict | None = None,
    decision_payload: dict | None = None,
    top_reasons: list[dict] | None = None,
) -> dict:
    return {
        "decision": decision,
        "score": risk_score,
        "thresholds": thresholds,
        "policy": policy_label,
        "factors": factors,
        "model": {
            "name": model_name,
            "version": model_version,
        },
        "matched_rules": matched_rules,
        "rule_explanations": rule_explanations,
        "inputs": ctx.to_payload(),
        "scoring": {
            "score": risk_score,
            "model_version": model_version,
        },
        "policy_details": policy,
        "decision_details": decision_payload,
        "top_reasons": top_reasons or [],
        "timestamps": {
            "evaluated_at": evaluated_at.isoformat(),
        },
    }
