from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
    scorer_payload = _build_scorer_payload(ctx, snapshot_features=snapshot.features, selector=selector)
    response: ScorerResponse | None = None
    error: str | None = None
    explain_payload: dict | None = None
    try:
        response = score(payload=scorer_payload)
    except Exception as exc:  # noqa: BLE001 - shadow must never impact v4
        logger.exception("risk_v5_shadow_score_failed", extra={"decision_id": risk_decision.decision_id})
        error = str(exc)
        explain_payload = {
            "degraded": True,
            "error": str(exc),
            "selector": selector,
            "features_hash": snapshot.features_hash,
            "provider_payload": _provider_payload_evidence(scorer_payload),
            "assumptions": ["shadow_only", "scorer_unavailable"],
        }
        response = None
    else:
        base_explain = dict(response.explain or {})
        assumptions = list(base_explain.get("assumptions") or [])
        if "shadow_only" not in assumptions:
            assumptions.append("shadow_only")
        explain_payload = {
            **base_explain,
            "degraded": bool(base_explain.get("degraded", False)),
            "selector": selector,
            "features_hash": snapshot.features_hash,
            "provider_payload": _provider_payload_evidence(scorer_payload),
            "assumptions": assumptions,
        }

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
        explain=explain_payload,
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
    if response.decision:
        return str(response.decision)
    return None


def _build_scorer_payload(
    ctx: RiskV5Context,
    *,
    snapshot_features: dict[str, Any],
    selector: str,
) -> dict[str, Any]:
    decision_context = ctx.decision_context
    metadata = dict(decision_context.metadata or {})
    history = dict(decision_context.history or {})
    amount = decision_context.amount if decision_context.amount is not None else snapshot_features.get("amount")
    operations_count = history.get("operations_count_30d", history.get("txn_count_24h"))
    avg_amount = history.get("avg_amount_30d", history.get("avg_amount_7d"))
    chargebacks = history.get("chargebacks")
    provider_metadata = {
        **metadata,
        "subject_type": ctx.subject_type.value,
        "subject_id": ctx.subject_id,
        "model_selector": selector,
        "features_schema": "risk_v5_shadow_features_v1",
        "features_keys": sorted(snapshot_features.keys()),
    }
    return {
        "amount": amount,
        "client_score": metadata.get("client_score"),
        "document_type": _provider_document_type(ctx),
        "client_status": metadata.get("client_status"),
        "history": {
            "operations_count_30d": operations_count,
            "chargebacks": chargebacks,
            "avg_amount_30d": avg_amount,
        },
        "metadata": provider_metadata,
    }


def _provider_document_type(ctx: RiskV5Context) -> str:
    metadata = ctx.decision_context.metadata or {}
    explicit = str(metadata.get("document_type") or "").strip().lower()
    allowed = {"invoice", "payout", "credit_note", "payment", "document", "export", "fuel_transaction"}
    if explicit in allowed:
        return explicit
    return {
        "PAYMENT": "payment",
        "INVOICE": "invoice",
        "PAYOUT": "payout",
        "DOCUMENT": "document",
        "EXPORT": "export",
        "FUEL_TRANSACTION": "fuel_transaction",
    }[ctx.subject_type.value]


def _provider_payload_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return {
        "schema": "ai_service_risk_score_v1",
        "amount_present": payload.get("amount") is not None,
        "document_type": payload.get("document_type"),
        "metadata_keys": sorted(metadata.keys()),
    }


__all__ = ["enqueue_shadow_decision"]
