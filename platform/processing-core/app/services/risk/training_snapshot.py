from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_training_snapshot import RiskTrainingSnapshot
from app.models.risk_types import RiskOutcome
from app.services.decision.context import DecisionContext


def capture_training_snapshot(
    db: Session,
    ctx: DecisionContext,
    *,
    decision_id: str,
    score: int,
    outcome: RiskOutcome,
    model_version: str | None,
    threshold_set: RiskThresholdSet | None,
    policy: RiskPolicy | None,
    evaluated_at: datetime,
) -> RiskTrainingSnapshot:
    context_payload = ctx.to_payload()
    features_payload = context_payload.copy()
    features_hash = _hash_payload(features_payload)
    thresholds_payload = _thresholds_payload(threshold_set)
    policy_payload = _policy_payload(policy)
    snapshot = RiskTrainingSnapshot(
        decision_id=decision_id,
        action=context_payload.get("action") or "UNKNOWN",
        score=score,
        outcome=outcome.value,
        model_version=model_version,
        features_hash=features_hash,
        context=context_payload,
        policy=policy_payload,
        thresholds=thresholds_payload,
        features=features_payload,
        created_at=evaluated_at,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def _hash_payload(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _policy_payload(policy: RiskPolicy | None) -> dict | None:
    if policy is None:
        return None
    return {
        "id": policy.id,
        "model_selector": policy.model_selector,
        "threshold_set_id": policy.threshold_set_id,
    }


def _thresholds_payload(threshold_set: RiskThresholdSet | None) -> dict:
    if threshold_set is None:
        return {"block": None, "review": None, "allow": None}
    return {
        "id": threshold_set.id,
        "block": threshold_set.block_threshold,
        "review": threshold_set.review_threshold,
        "allow": threshold_set.allow_threshold,
        "currency": threshold_set.currency,
        "valid_from": threshold_set.valid_from.isoformat() if threshold_set.valid_from else None,
        "valid_to": threshold_set.valid_to.isoformat() if threshold_set.valid_to else None,
    }


__all__ = ["capture_training_snapshot"]
