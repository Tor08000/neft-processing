from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger

from app.models.risk_decision import RiskDecision
from app.models.risk_v5_shadow_decision import RiskV5ShadowDecision
from app.services.risk_v5.ab import resolve_assignment
from app.services.risk_v5.context import RiskV5Context
from app.services.risk_v5.feature_store import build_feature_snapshot
from app.services.risk_v5.metrics import metrics
from app.services.risk_v5.registry_client import model_selector
from app.services.risk_v5.scorer_client import ScorerResponse, score

logger = get_logger(__name__)


def enqueue_shadow_decision(
    db: Session,
    risk_decision: RiskDecision,
) -> RiskV5ShadowDecision | None:
    payload = risk_decision.features_snapshot or {}
    if not payload:
        logger.warning("risk_v5_shadow_missing_context", extra={"decision_id": risk_decision.decision_id})
        return None
    ctx = RiskV5Context.from_payload(payload)
    assignment = resolve_assignment(
        db,
        tenant_id=payload.get("tenant_id"),
        client_id=payload.get("client_id"),
        subject_type=ctx.subject_type,
    )
    if assignment.bucket != "B":
        return None

    snapshot = build_feature_snapshot(ctx.decision_context)
    selector = model_selector(ctx.subject_type)
    response: ScorerResponse | None = None
    error: str | None = None
    try:
        response = score(
            payload={
                "subject_type": ctx.subject_type.value,
                "subject_id": ctx.subject_id,
                "tenant_id": payload.get("tenant_id"),
                "client_id": payload.get("client_id"),
                "features_snapshot": snapshot.features,
                "model_selector": selector,
            }
        )
    except Exception as exc:  # noqa: BLE001 - shadow must never impact v4
        logger.exception("risk_v5_shadow_score_failed", extra={"decision_id": risk_decision.decision_id})
        error = "ai_unavailable"
        response = None

    created_at = risk_decision.decided_at or datetime.now(timezone.utc)
    record = RiskV5ShadowDecision(
        decision_id=risk_decision.decision_id,
        tenant_id=payload.get("tenant_id"),
        client_id=payload.get("client_id"),
        subject_type=ctx.subject_type,
        subject_id=ctx.subject_id,
        v4_score=risk_decision.score,
        v4_outcome=risk_decision.outcome,
        v4_policy_id=risk_decision.policy_id,
        v4_threshold_set_id=risk_decision.threshold_set_id,
        v5_score=response.score if response else None,
        v5_predicted_outcome=_predicted_outcome(response),
        v5_model_version=response.model_version if response else None,
        v5_selector=selector,
        features_schema_version=snapshot.schema_version,
        features_hash=snapshot.features_hash,
        features_snapshot=snapshot.features,
        explain=response.explain if response else None,
        error=error,
        created_at=created_at,
    )
    db.add(record)
    db.flush()

    metrics.observe_score(record.v5_score)
    metrics.observe_predicted(record.v5_predicted_outcome)
    metrics.observe_decision(
        v4_outcome=risk_decision.outcome.value,
        v5_outcome=record.v5_predicted_outcome,
    )
    return record


def _predicted_outcome(response: ScorerResponse | None) -> str | None:
    if response is None:
        return None
    explain = response.explain or {}
    predicted = explain.get("predicted_outcome")
    if predicted:
        return str(predicted)
    return None


__all__ = ["enqueue_shadow_decision"]
