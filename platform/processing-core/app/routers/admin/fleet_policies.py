from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fuel import FleetActionPolicy, FleetPolicyExecution
from app.schemas.admin.fleet_policies import (
    AdminFleetActionPolicyListResponse,
    AdminFleetActionPolicyOut,
    AdminFleetCardUnblockIn,
    AdminFleetPolicyExecutionListResponse,
    AdminFleetPolicyExecutionOut,
)
from app.services.admin_auth import require_admin
from app.security.rbac.principal import Principal
from app.services.audit_service import request_context_from_request
from app.services.fuel import events as fuel_events
from app.services.policy import actor_from_token
from app.services import fleet_service

router = APIRouter(prefix="/fleet", tags=["admin", "fleet"])


@router.get("/policies", response_model=AdminFleetActionPolicyListResponse)
def list_action_policies(
    client_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> AdminFleetActionPolicyListResponse:
    _ = token
    policies = (
        db.query(FleetActionPolicy)
        .filter(FleetActionPolicy.client_id == client_id)
        .order_by(FleetActionPolicy.created_at.desc())
        .all()
    )
    return AdminFleetActionPolicyListResponse(
        items=[
            AdminFleetActionPolicyOut(
                id=str(policy.id),
                client_id=policy.client_id,
                scope_type=policy.scope_type,
                scope_id=str(policy.scope_id) if policy.scope_id else None,
                trigger_type=policy.trigger_type,
                trigger_severity_min=policy.trigger_severity_min,
                breach_kind=policy.breach_kind,
                action=policy.action,
                cooldown_seconds=policy.cooldown_seconds,
                active=policy.active,
                created_at=policy.created_at,
            )
            for policy in policies
        ]
    )


@router.get("/executions", response_model=AdminFleetPolicyExecutionListResponse)
def list_policy_executions(
    client_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> AdminFleetPolicyExecutionListResponse:
    _ = token
    executions = (
        db.query(FleetPolicyExecution)
        .filter(FleetPolicyExecution.client_id == client_id)
        .order_by(FleetPolicyExecution.created_at.desc())
        .all()
    )
    return AdminFleetPolicyExecutionListResponse(
        items=[
            AdminFleetPolicyExecutionOut(
                id=str(execution.id),
                client_id=execution.client_id,
                policy_id=str(execution.policy_id),
                event_type=execution.event_type,
                event_id=str(execution.event_id),
                action=execution.action,
                status=execution.status,
                reason=execution.reason,
                created_at=execution.created_at,
            )
            for execution in executions
        ]
    )


@router.post("/cards/{card_id}/unblock")
def admin_unblock_card(
    card_id: str,
    payload: AdminFleetCardUnblockIn,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> dict:
    actor = actor_from_token(token)
    if not actor.is_admin:
        raise HTTPException(status_code=403, detail="forbidden")
    ctx = request_context_from_request(request, token=token)
    principal = Principal(
        user_id=actor.user_id,
        roles=actor.roles,
        scopes=set(),
        client_id=None,
        partner_id=None,
        is_admin=True,
        raw_claims={"subject_type": "admin"},
    )
    card = fleet_service.unblock_card_with_reason(
        db,
        card_id=card_id,
        reason=payload.reason,
        principal=principal,
        request_id=ctx.request_id,
        trace_id=ctx.trace_id,
    )
    db.commit()
    fuel_events.audit_event(
        db,
        event_type=fuel_events.FUEL_EVENT_CARD_UPDATED,
        entity_id=str(card.id),
        payload={"status": card.status.value, "reason": payload.reason},
        request_ctx=ctx,
    )
    return {"card_id": str(card.id), "status": card.status.value}
