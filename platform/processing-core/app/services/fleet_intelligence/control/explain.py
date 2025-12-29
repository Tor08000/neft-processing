from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.fleet_intelligence_actions import FIInsight, FIInsightEntityType, FIInsightStatus
from app.services.fleet_intelligence.control import auto_resolution, confidence as control_confidence
from app.services.fleet_intelligence.control import repository
from app.services.fleet_intelligence.control.defaults import CONFIDENCE_WINDOW_DAYS, CONF_HALF_LIFE_DAYS
from app.services.fleet_intelligence.policies import registry as policy_registry


ACTIVE_STATUSES = {
    FIInsightStatus.OPEN,
    FIInsightStatus.ACKED,
    FIInsightStatus.ACTION_PLANNED,
    FIInsightStatus.ACTION_APPLIED,
    FIInsightStatus.MONITORING,
}


def build_fleet_control_section(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
) -> dict[str, Any] | None:
    insight = _find_active_insight(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        station_id=station_id,
    )
    if not insight:
        return None
    suggested = repository.list_suggested_actions(db, insight_id=str(insight.id))
    action_codes = [action.action_code for action in suggested]
    improved_counts = repository.action_improvement_counts(db, action_codes=action_codes)
    now = datetime.now(timezone.utc)
    confidence_map = {
        action_code: control_confidence.compute_action_confidence(db, action_code=action_code, now=now)
        for action_code in action_codes
    }
    last_action = repository.get_latest_applied_action(db, insight_id=str(insight.id))
    effect_label = None
    if last_action:
        effects = repository.list_action_effects(db, applied_action_id=str(last_action.id))
        if effects:
            effect_label = effects[0].effect_label
    last_action_confidence = (
        control_confidence.compute_action_confidence(db, action_code=last_action.action_code, now=now)
        if last_action
        else None
    )
    auto_resolution_hint = auto_resolution.build_auto_resolution_hint(
        effect_label=effect_label,
        confidence=last_action_confidence,
    )
    aging = auto_resolution.build_insight_aging(insight, effect_label=effect_label)
    return {
        "active_insight": _serialize_insight(insight),
        "suggested_actions": [
            _serialize_suggested_action(
                action,
                improved_count=improved_counts.get(action.action_code, 0),
                confidence=confidence_map.get(action.action_code),
            )
            for action in suggested
        ],
        "last_action": _serialize_applied_action(last_action) if last_action else None,
        "effect": effect_label.value if effect_label else None,
        "auto_resolution_hint": auto_resolution_hint,
        "aging": aging,
    }


def build_fleet_control_snapshot(db: Session, *, insight_id: str) -> dict[str, Any] | None:
    insight = repository.get_insight(db, insight_id=insight_id)
    if not insight:
        return None
    suggested = repository.list_suggested_actions(db, insight_id=str(insight.id))
    now = datetime.now(timezone.utc)
    confidence_map = {
        action.action_code: control_confidence.compute_action_confidence(db, action_code=action.action_code, now=now)
        for action in suggested
    }
    section = {
        "active_insight": _serialize_insight(insight),
        "suggested_actions": [
            _serialize_suggested_action(
                action,
                confidence=confidence_map.get(action.action_code),
            )
            for action in suggested
        ],
        "last_action": _serialize_applied_action(repository.get_latest_applied_action(db, insight_id=str(insight.id))),
    }
    return {
        "subject": {"type": "FI_INSIGHT", "id": str(insight.id)},
        "sections": {"fleet_control": section},
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _find_active_insight(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
) -> FIInsight | None:
    query = (
        db.query(FIInsight)
        .filter(FIInsight.tenant_id == tenant_id)
        .filter(FIInsight.client_id == client_id)
        .filter(FIInsight.status.in_(ACTIVE_STATUSES))
    )
    if driver_id:
        query = query.filter(FIInsight.entity_type == FIInsightEntityType.DRIVER).filter(
            FIInsight.entity_id == driver_id
        )
    elif vehicle_id:
        query = query.filter(FIInsight.entity_type == FIInsightEntityType.VEHICLE).filter(
            FIInsight.entity_id == vehicle_id
        )
    elif station_id:
        query = query.filter(FIInsight.entity_type == FIInsightEntityType.STATION).filter(
            FIInsight.entity_id == station_id
        )
    else:
        return None
    return query.order_by(FIInsight.created_at.desc()).first()


def _serialize_insight(insight: FIInsight) -> dict[str, Any]:
    return {
        "id": str(insight.id),
        "type": insight.insight_type.value,
        "entity_type": insight.entity_type.value,
        "entity_id": str(insight.entity_id),
        "window_days": insight.window_days,
        "severity": insight.severity.value,
        "status": insight.status.value,
        "summary": insight.summary,
        "created_at": insight.created_at.isoformat() if insight.created_at else None,
    }


def _serialize_suggested_action(
    action,
    *,
    improved_count: int | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    payload = action.payload if isinstance(action.payload, dict) else {}
    confidence_status = auto_resolution.confidence_status(confidence)
    confidence_recommendation = auto_resolution.build_confidence_recommendation(confidence)
    return {
        "id": str(action.id),
        "action_code": action.action_code.value,
        "target_system": action.target_system.value,
        "status": action.status.value,
        "payload": action.payload,
        "confidence_improved_count": improved_count,
        "confidence": confidence,
        "confidence_status": confidence_status,
        "confidence_recommendation": confidence_recommendation,
        "confidence_window_days": CONFIDENCE_WINDOW_DAYS,
        "confidence_half_life_days": CONF_HALF_LIFE_DAYS,
        "bundle_code": payload.get("bundle_code"),
        "step_index": payload.get("step_index"),
        "params": payload.get("params"),
    }


def _serialize_applied_action(action) -> dict[str, Any] | None:
    if not action:
        return None
    return {
        "id": str(action.id),
        "action_code": action.action_code.value,
        "status": action.status.value,
        "applied_at": action.applied_at.isoformat() if action.applied_at else None,
        "reason_code": action.reason_code,
        "reason_text": action.reason_text,
    }


def build_fleet_policy_bundle_section(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
) -> dict[str, Any] | None:
    insight = _find_active_insight(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        station_id=station_id,
    )
    if not insight:
        return None
    bundle = policy_registry.match_bundle_for_insight(insight)
    if not bundle:
        return None
    return policy_registry.serialize_bundle(bundle)


__all__ = ["build_fleet_control_section", "build_fleet_control_snapshot", "build_fleet_policy_bundle_section"]
