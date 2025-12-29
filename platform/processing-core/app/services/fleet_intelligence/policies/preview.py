from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.fleet_intelligence_actions import FIInsight, FIInsightStatus
from app.services.fleet_intelligence.control import auto_resolution, confidence as control_confidence
from app.services.fleet_intelligence.policies import bundles, registry


ACTIVE_STATUSES = {
    FIInsightStatus.OPEN,
    FIInsightStatus.ACKED,
    FIInsightStatus.ACTION_PLANNED,
    FIInsightStatus.ACTION_APPLIED,
    FIInsightStatus.MONITORING,
}


def build_policy_bundle_preview(
    db: Session,
    *,
    bundle_code: str,
    client_id: str | None = None,
    status: FIInsightStatus | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    bundle = _get_bundle(bundle_code)
    if not bundle:
        raise ValueError("bundle_not_found")
    insights = _find_matching_insights(db, bundle=bundle, client_id=client_id, status=status, limit=limit)
    actions = []
    for index, step in enumerate(bundle.steps):
        actions.append(
            {
                "action_code": step.action_code,
                "target_system": step.target_system,
                "payload": step.action_payload,
                "params": step.params,
                "step_index": index,
            }
        )
    confidence_preview = _build_confidence_preview(db, bundle=bundle)
    return {
        "bundle": registry.serialize_bundle(bundle),
        "affected_insights": insights,
        "actions": actions,
        "confidence_preview": confidence_preview,
    }


def _get_bundle(bundle_code: str) -> bundles.ScenarioBundle | None:
    for bundle in bundles.BUNDLES:
        if bundle.bundle_code == bundle_code:
            return bundle
    return None


def _find_matching_insights(
    db: Session,
    *,
    bundle: bundles.ScenarioBundle,
    client_id: str | None,
    status: FIInsightStatus | None,
    limit: int,
) -> list[FIInsight]:
    statuses = {status} if status else ACTIVE_STATUSES
    query = db.query(FIInsight).filter(FIInsight.status.in_(statuses))
    if client_id:
        query = query.filter(FIInsight.client_id == client_id)
    results = []
    for insight in query.order_by(FIInsight.created_at.desc()).limit(limit).all():
        if _matches_bundle(insight, bundle=bundle):
            results.append(insight)
    return results


def _matches_bundle(insight: FIInsight, *, bundle: bundles.ScenarioBundle) -> bool:
    for trigger in bundle.triggers:
        if insight.insight_type == trigger.insight_type and insight.severity == trigger.severity:
            return True
    return False


def _build_confidence_preview(db: Session, *, bundle: bundles.ScenarioBundle) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    seen = set()
    preview = []
    for step in bundle.steps:
        if step.action_code in seen:
            continue
        seen.add(step.action_code)
        confidence = control_confidence.compute_action_confidence(
            db,
            action_code=step.action_code,
            now=now,
        )
        preview.append(
            {
                "action_code": step.action_code,
                "confidence": confidence,
                "confidence_status": auto_resolution.confidence_status(confidence),
            }
        )
    return preview


__all__ = ["build_policy_bundle_preview"]
