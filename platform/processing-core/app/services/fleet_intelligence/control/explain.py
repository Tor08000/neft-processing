from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.fleet_intelligence_actions import FIInsight, FIInsightEntityType, FIInsightStatus
from app.services.fleet_intelligence.control import repository


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
    last_action = repository.get_latest_applied_action(db, insight_id=str(insight.id))
    effect_label = None
    if last_action:
        effects = repository.list_action_effects(db, applied_action_id=str(last_action.id))
        if effects:
            effect_label = effects[0].effect_label.value
    return {
        "active_insight": _serialize_insight(insight),
        "suggested_actions": [_serialize_suggested_action(action) for action in suggested],
        "last_action": _serialize_applied_action(last_action) if last_action else None,
        "effect": effect_label,
    }


def build_fleet_control_snapshot(db: Session, *, insight_id: str) -> dict[str, Any] | None:
    insight = repository.get_insight(db, insight_id=insight_id)
    if not insight:
        return None
    section = {
        "active_insight": _serialize_insight(insight),
        "suggested_actions": [
            _serialize_suggested_action(action)
            for action in repository.list_suggested_actions(db, insight_id=str(insight.id))
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


def _serialize_suggested_action(action) -> dict[str, Any]:
    return {
        "id": str(action.id),
        "action_code": action.action_code.value,
        "target_system": action.target_system.value,
        "status": action.status.value,
        "payload": action.payload,
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


__all__ = ["build_fleet_control_section", "build_fleet_control_snapshot"]
