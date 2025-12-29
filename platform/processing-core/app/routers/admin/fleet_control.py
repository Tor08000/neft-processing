from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.schemas.admin.fleet_control import (
    FleetControlActionDecisionIn,
    FleetControlActionEffectOut,
    FleetControlAppliedActionOut,
    FleetControlInsightDetailOut,
    FleetControlInsightOut,
    FleetControlSuggestedActionOut,
)
from app.models.fleet_intelligence_actions import FIInsightStatus
from app.services.fleet_intelligence.control import actions as control_actions
from app.services.fleet_intelligence.control import repository as control_repository

router = APIRouter(prefix="/fleet-control", tags=["admin", "fleet-control"])


@router.get("/insights", response_model=list[FleetControlInsightOut])
def list_insights(
    *,
    client_id: str | None = Query(None),
    status: FIInsightStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> list[FleetControlInsightOut]:
    items = control_repository.list_insights(db, client_id=client_id, status=status)
    return [FleetControlInsightOut.model_validate(item) for item in items]


@router.get("/insights/{insight_id}", response_model=FleetControlInsightDetailOut)
def get_insight_detail(
    *,
    insight_id: str,
    db: Session = Depends(get_db),
) -> FleetControlInsightDetailOut:
    insight = control_repository.get_insight(db, insight_id=insight_id)
    if not insight:
        raise HTTPException(status_code=404, detail="insight_not_found")
    suggested = control_repository.list_suggested_actions(db, insight_id=insight_id)
    applied = control_repository.list_applied_actions(db, insight_id=insight_id)
    effects = []
    for item in applied:
        effects.extend(control_repository.list_action_effects(db, applied_action_id=str(item.id)))
    return FleetControlInsightDetailOut(
        insight=FleetControlInsightOut.model_validate(insight),
        suggested_actions=[FleetControlSuggestedActionOut.model_validate(item) for item in suggested],
        applied_actions=[FleetControlAppliedActionOut.model_validate(item) for item in applied],
        effects=[FleetControlActionEffectOut.model_validate(item) for item in effects],
    )


@router.post("/actions/{action_id}/approve", response_model=FleetControlSuggestedActionOut)
def approve_action(
    *,
    action_id: str,
    payload: FleetControlActionDecisionIn,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> FleetControlSuggestedActionOut:
    action = control_repository.get_suggested_action(db, action_id=action_id)
    if not action:
        raise HTTPException(status_code=404, detail="action_not_found")
    actor = token.get("user_id") or token.get("email")
    try:
        control_actions.approve_suggested_action(
            db,
            action=action,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            actor=actor,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FleetControlSuggestedActionOut.model_validate(action)


@router.post("/actions/{action_id}/apply", response_model=FleetControlAppliedActionOut)
def apply_action(
    *,
    action_id: str,
    payload: FleetControlActionDecisionIn,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> FleetControlAppliedActionOut:
    action = control_repository.get_suggested_action(db, action_id=action_id)
    if not action:
        raise HTTPException(status_code=404, detail="action_not_found")
    actor = token.get("user_id") or token.get("email")
    try:
        applied = control_actions.apply_suggested_action(
            db,
            action=action,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            actor=actor,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FleetControlAppliedActionOut.model_validate(applied)


__all__ = ["router"]
