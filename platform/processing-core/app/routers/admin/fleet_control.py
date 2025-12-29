from __future__ import annotations

from datetime import datetime, timezone

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
from app.models.fleet_intelligence_actions import FIActionEffectLabel, FIInsightStatus
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
    action_codes = [action.action_code for action in suggested]
    improved_counts = control_repository.action_improvement_counts(db, action_codes=action_codes)
    applied = control_repository.list_applied_actions(db, insight_id=insight_id)
    effects = []
    latest_effect_label = None
    for item in applied:
        effect_items = control_repository.list_action_effects(db, applied_action_id=str(item.id))
        effects.extend(effect_items)
        if effect_items and not latest_effect_label:
            latest_effect_label = effect_items[0].effect_label
    auto_resolution_hint = _build_auto_resolution_hint(latest_effect_label)
    aging = _build_insight_aging(insight, has_effects=bool(effects))
    return FleetControlInsightDetailOut(
        insight=FleetControlInsightOut.model_validate(insight),
        suggested_actions=[
            FleetControlSuggestedActionOut.model_validate(
                {
                    **FleetControlSuggestedActionOut.model_validate(item).model_dump(),
                    "confidence_improved_count": improved_counts.get(item.action_code, 0),
                }
            )
            for item in suggested
        ],
        applied_actions=[FleetControlAppliedActionOut.model_validate(item) for item in applied],
        effects=[FleetControlActionEffectOut.model_validate(item) for item in effects],
        auto_resolution_hint=auto_resolution_hint,
        aging=aging,
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


def _build_auto_resolution_hint(effect_label: FIActionEffectLabel | None) -> dict[str, str] | None:
    if effect_label == FIActionEffectLabel.IMPROVED:
        return {
            "code": "SUGGEST_CLOSE_INSIGHT",
            "message": "Эффект улучшился — можно закрыть инсайт.",
        }
    if effect_label == FIActionEffectLabel.NO_CHANGE:
        return {
            "code": "SUGGEST_AMPLIFY_ACTION",
            "message": "Нет изменений — усилить действие или выбрать другую меру.",
        }
    return None


def _build_insight_aging(insight, *, has_effects: bool) -> dict[str, str | int | bool] | None:
    if not insight.created_at:
        return None
    now = datetime.now(timezone.utc)
    created_at = insight.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    days_open = max((now - created_at).days, 0)
    needs_escalation = not has_effects and days_open >= 14
    if not needs_escalation:
        return {"days_open": days_open, "needs_escalation": False}
    return {"days_open": days_open, "needs_escalation": True, "reason": "insight_no_effect_14d"}
