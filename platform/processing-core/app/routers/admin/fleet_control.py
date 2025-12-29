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
    FleetPolicyPreviewAction,
    FleetPolicyPreviewConfidence,
    FleetPolicyPreviewIn,
    FleetPolicyPreviewInsight,
    FleetPolicyPreviewOut,
)
from app.models.fleet_intelligence_actions import FIInsightStatus
from app.services.fleet_intelligence.control import actions as control_actions
from app.services.fleet_intelligence.control import auto_resolution, confidence as control_confidence
from app.services.fleet_intelligence.control import repository as control_repository
from app.services.fleet_intelligence.policies import preview as policy_preview

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
    now = datetime.now(timezone.utc)
    confidence_map = {
        action.action_code: control_confidence.compute_action_confidence(db, action_code=action.action_code, now=now)
        for action in suggested
    }
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
    last_action = applied[0] if applied else None
    last_action_confidence = (
        control_confidence.compute_action_confidence(db, action_code=last_action.action_code, now=now)
        if last_action
        else None
    )
    auto_resolution_hint = auto_resolution.build_auto_resolution_hint(
        effect_label=latest_effect_label,
        confidence=last_action_confidence,
    )
    aging = auto_resolution.build_insight_aging(insight, effect_label=latest_effect_label)
    return FleetControlInsightDetailOut(
        insight=FleetControlInsightOut.model_validate(insight),
        suggested_actions=[
            FleetControlSuggestedActionOut.model_validate(
                {
                    **FleetControlSuggestedActionOut.model_validate(item).model_dump(),
                    "confidence_improved_count": improved_counts.get(item.action_code, 0),
                    "confidence": confidence_map.get(item.action_code),
                    "confidence_status": auto_resolution.confidence_status(
                        confidence_map.get(item.action_code)
                    ),
                    "confidence_recommendation": auto_resolution.build_confidence_recommendation(
                        confidence_map.get(item.action_code)
                    ),
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


@router.post("/preview", response_model=FleetPolicyPreviewOut)
def preview_policy_bundle(
    payload: FleetPolicyPreviewIn,
    db: Session = Depends(get_db),
) -> FleetPolicyPreviewOut:
    try:
        preview_payload = policy_preview.build_policy_bundle_preview(
            db,
            bundle_code=payload.bundle_code,
            client_id=payload.client_id,
            status=payload.status,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FleetPolicyPreviewOut(
        bundle=preview_payload["bundle"],
        affected_insights=[
            FleetPolicyPreviewInsight.model_validate(item) for item in preview_payload["affected_insights"]
        ],
        actions=[FleetPolicyPreviewAction.model_validate(item) for item in preview_payload["actions"]],
        confidence_preview=[
            FleetPolicyPreviewConfidence.model_validate(item)
            for item in preview_payload["confidence_preview"]
        ],
    )


__all__ = ["router"]
