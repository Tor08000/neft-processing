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
    context_hash: str,
    scoring_source: str | None,
    scoring_assumptions: list[str] | None = None,
    scoring_evidence: dict | None = None,
    policy: dict | None = None,
    decision_payload: dict | None = None,
    top_reasons: list[dict] | None = None,
    record_refs: dict | None = None,
    audit: dict | None = None,
    graph: dict | None = None,
) -> dict:
    """Build the canonical explain payload for deterministic decision inspection."""
    normalized_factors = factors or ["no_factors"]
    normalized_assumptions = scoring_assumptions or []
    scoring_trace = {
        "source": scoring_source,
        "score": risk_score,
        "context_hash": context_hash,
        "thresholds": thresholds,
        "decision": decision,
        "model": {
            "name": model_name,
            "version": model_version,
        },
        "assumptions": normalized_assumptions,
        "evidence": scoring_evidence or {},
        "policy": policy,
        "decision_details": decision_payload,
    }
    scoring_trace_hash = _hash_decision_payload(scoring_trace)
    explain_payload = {
        "decision": decision,
        "score": risk_score,
        "context_hash": context_hash,
        "scoring_trace_hash": scoring_trace_hash,
        "thresholds": thresholds,
        "policy": policy_label,
        "policy_id": policy_label,
        "factors": normalized_factors,
        "assumptions": normalized_assumptions,
        "model": {
            "name": model_name,
            "version": model_version,
        },
        "pipeline": {
            "input": "decision_context",
            "rules": "deterministic_rules",
            "score_source": scoring_source,
            "scoring_trace_hash": scoring_trace_hash,
            "explain": "decision_explain_v1",
            "audit": "risk_decision_audit",
        },
        "matched_rules": matched_rules,
        "rule_explanations": rule_explanations,
        "inputs": ctx.to_payload(),
        "scoring": {
            "score": risk_score,
            "model_version": model_version,
            "source": scoring_source,
            "assumptions": normalized_assumptions,
            "evidence": scoring_evidence or {},
            "trace": scoring_trace,
            "trace_hash": scoring_trace_hash,
        },
        "policy_details": policy,
        "decision_details": decision_payload,
        "top_reasons": top_reasons or [],
        "record_refs": record_refs or {},
        "audit": audit or {},
        "graph": graph or {},
        "timestamps": {
            "evaluated_at": evaluated_at.isoformat(),
        },
    }
    explain_payload["decision_hash"] = _hash_decision_payload(
        {
            "decision": decision,
            "score": risk_score,
            "context_hash": context_hash,
            "thresholds": thresholds,
            "policy": policy_label,
            "factors": normalized_factors,
            "assumptions": normalized_assumptions,
            "model": {
                "name": model_name,
                "version": model_version,
            },
            "scoring": {
                "source": scoring_source,
                "evidence": scoring_evidence or {},
            },
            "policy_details": policy,
            "decision_details": decision_payload,
        }
    )
    return explain_payload


def _hash_decision_payload(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
