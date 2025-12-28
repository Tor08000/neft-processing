from __future__ import annotations

from datetime import datetime
import hashlib
import json

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
    """Build the canonical explain payload for deterministic decision inspection."""
    normalized_factors = factors or ["no_factors"]
    explain_payload = {
        "decision": decision,
        "score": risk_score,
        "thresholds": thresholds,
        "policy": policy_label,
        "policy_id": policy_label,
        "factors": normalized_factors,
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
    explain_payload["decision_hash"] = _hash_decision_payload(
        {
            "decision": decision,
            "score": risk_score,
            "thresholds": thresholds,
            "policy": policy_label,
            "factors": normalized_factors,
            "model": {
                "name": model_name,
                "version": model_version,
            },
            "policy_details": policy,
            "decision_details": decision_payload,
        }
    )
    return explain_payload


def _hash_decision_payload(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
