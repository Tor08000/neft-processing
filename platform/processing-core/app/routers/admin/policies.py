from __future__ import annotations

from datetime import datetime
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fuel import (
    FleetActionPolicy,
    FleetActionPolicyAction,
    FleetActionPolicyScopeType,
    FleetActionTriggerType,
    FleetNotificationSeverity,
    FleetPolicyExecution,
)
from app.models.risk_policy import RiskPolicy
from app.schemas.admin.policies import (
    AdminPolicyDetailResponse,
    AdminPolicyExecutionListResponse,
    AdminPolicyExecutionOut,
    AdminPolicyHeader,
    AdminPolicyIndexItem,
    AdminPolicyIndexResponse,
    PolicyExplainRef,
    PolicyScope,
    PolicyStatus,
    PolicyType,
)

router = APIRouter(prefix="/policies", tags=["admin-policies"])


def _policy_status(is_active: bool) -> PolicyStatus:
    return PolicyStatus.ENABLED if is_active else PolicyStatus.DISABLED


def _fleet_policy_title(policy: FleetActionPolicy) -> str:
    trigger = policy.trigger_type.value if hasattr(policy.trigger_type, "value") else str(policy.trigger_type)
    action = policy.action.value if hasattr(policy.action, "value") else str(policy.action)
    return f"{trigger} → {action}"


def _fleet_policy_actions(policy: FleetActionPolicy) -> list[str]:
    action = policy.action.value if hasattr(policy.action, "value") else str(policy.action)
    trigger = policy.trigger_type.value if hasattr(policy.trigger_type, "value") else str(policy.trigger_type)
    return [action, trigger]


def _risk_policy_title(policy: RiskPolicy) -> str:
    subject = policy.subject_type.value if hasattr(policy.subject_type, "value") else str(policy.subject_type)
    return f"Risk policy · {subject}"


def _risk_policy_actions(policy: RiskPolicy) -> list[str]:
    subject = policy.subject_type.value if hasattr(policy.subject_type, "value") else str(policy.subject_type)
    return ["RISK_THRESHOLD", f"SUBJECT:{subject}"]


def _filter_by_status(items: Iterable[AdminPolicyIndexItem], status: PolicyStatus | None) -> list[AdminPolicyIndexItem]:
    if status is None:
        return list(items)
    return [item for item in items if item.status == status]


def _filter_by_query(items: Iterable[AdminPolicyIndexItem], query: str | None) -> list[AdminPolicyIndexItem]:
    if not query:
        return list(items)
    lowered = query.lower()
    filtered: list[AdminPolicyIndexItem] = []
    for item in items:
        action_match = any(lowered in action.lower() for action in item.actions)
        if lowered in item.id.lower() or lowered in item.title.lower() or action_match:
            filtered.append(item)
    return filtered


@router.get("", response_model=AdminPolicyIndexResponse)
def list_policies(
    type: PolicyType | None = Query(None),
    status: PolicyStatus | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AdminPolicyIndexResponse:
    items: list[AdminPolicyIndexItem] = []

    if type in (None, PolicyType.FLEET):
        fleet_policies = db.query(FleetActionPolicy).order_by(FleetActionPolicy.created_at.desc()).all()
        items.extend(
            AdminPolicyIndexItem(
                id=str(policy.id),
                type=PolicyType.FLEET,
                title=_fleet_policy_title(policy),
                status=_policy_status(policy.active),
                scope=PolicyScope(tenant_id=None, client_id=policy.client_id),
                actions=_fleet_policy_actions(policy),
                explain_ref=PolicyExplainRef(kind="policy", id=str(policy.id), type=PolicyType.FLEET),
                updated_at=policy.created_at,
                toggle_supported=True,
            )
            for policy in fleet_policies
        )

    if type in (None, PolicyType.FINANCE):
        risk_policies = db.query(RiskPolicy).order_by(RiskPolicy.priority.asc(), RiskPolicy.id.asc()).all()
        items.extend(
            AdminPolicyIndexItem(
                id=str(policy.id),
                type=PolicyType.FINANCE,
                title=_risk_policy_title(policy),
                status=_policy_status(policy.active),
                scope=PolicyScope(tenant_id=policy.tenant_id, client_id=policy.client_id),
                actions=_risk_policy_actions(policy),
                explain_ref=PolicyExplainRef(kind="policy", id=str(policy.id), type=PolicyType.FINANCE),
                updated_at=None,
                toggle_supported=True,
            )
            for policy in risk_policies
        )

    items = _filter_by_status(items, status)
    items = _filter_by_query(items, q)

    items.sort(key=lambda item: item.updated_at or datetime.min, reverse=True)
    total = len(items)
    paged = items[offset : offset + limit]
    return AdminPolicyIndexResponse(items=paged, total=total, limit=limit, offset=offset)


@router.get("/{policy_type}/{policy_id}", response_model=AdminPolicyDetailResponse)
def get_policy_detail(
    policy_type: PolicyType = Path(..., alias="policy_type"),
    policy_id: str = Path(..., alias="policy_id"),
    db: Session = Depends(get_db),
) -> AdminPolicyDetailResponse:
    if policy_type == PolicyType.FLEET:
        policy = db.query(FleetActionPolicy).filter(FleetActionPolicy.id == policy_id).one_or_none()
        if not policy:
            raise HTTPException(status_code=404, detail="policy_not_found")
        header = AdminPolicyHeader(
            id=str(policy.id),
            type=PolicyType.FLEET,
            title=_fleet_policy_title(policy),
            status=_policy_status(policy.active),
            scope=PolicyScope(tenant_id=None, client_id=policy.client_id),
            actions=_fleet_policy_actions(policy),
            updated_at=policy.created_at,
            toggle_supported=True,
        )
        payload = {
            "id": str(policy.id),
            "client_id": policy.client_id,
            "scope_type": policy.scope_type.value if isinstance(policy.scope_type, FleetActionPolicyScopeType) else policy.scope_type,
            "scope_id": str(policy.scope_id) if policy.scope_id else None,
            "trigger_type": policy.trigger_type.value
            if isinstance(policy.trigger_type, FleetActionTriggerType)
            else policy.trigger_type,
            "trigger_severity_min": policy.trigger_severity_min.value
            if isinstance(policy.trigger_severity_min, FleetNotificationSeverity)
            else policy.trigger_severity_min,
            "breach_kind": policy.breach_kind.value if policy.breach_kind else None,
            "action": policy.action.value if isinstance(policy.action, FleetActionPolicyAction) else policy.action,
            "cooldown_seconds": policy.cooldown_seconds,
            "active": policy.active,
            "created_at": policy.created_at,
        }
        return AdminPolicyDetailResponse(header=header, policy=payload, explain=None)

    if policy_type == PolicyType.FINANCE:
        policy = db.query(RiskPolicy).filter(RiskPolicy.id == policy_id).one_or_none()
        if not policy:
            raise HTTPException(status_code=404, detail="policy_not_found")
        header = AdminPolicyHeader(
            id=str(policy.id),
            type=PolicyType.FINANCE,
            title=_risk_policy_title(policy),
            status=_policy_status(policy.active),
            scope=PolicyScope(tenant_id=policy.tenant_id, client_id=policy.client_id),
            actions=_risk_policy_actions(policy),
            updated_at=None,
            toggle_supported=True,
        )
        payload = {
            "id": policy.id,
            "subject_type": policy.subject_type.value if hasattr(policy.subject_type, "value") else policy.subject_type,
            "tenant_id": policy.tenant_id,
            "client_id": policy.client_id,
            "provider": policy.provider,
            "currency": policy.currency,
            "country": policy.country,
            "threshold_set_id": policy.threshold_set_id,
            "model_selector": policy.model_selector,
            "priority": policy.priority,
            "active": policy.active,
        }
        return AdminPolicyDetailResponse(header=header, policy=payload, explain=None)

    raise HTTPException(status_code=404, detail="policy_not_found")


@router.get("/{policy_type}/{policy_id}/executions", response_model=AdminPolicyExecutionListResponse)
def list_policy_executions(
    policy_type: PolicyType = Path(..., alias="policy_type"),
    policy_id: str = Path(..., alias="policy_id"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AdminPolicyExecutionListResponse:
    if policy_type != PolicyType.FLEET:
        return AdminPolicyExecutionListResponse(items=[])
    executions = (
        db.query(FleetPolicyExecution)
        .filter(FleetPolicyExecution.policy_id == policy_id)
        .order_by(FleetPolicyExecution.created_at.desc())
        .limit(limit)
        .all()
    )
    return AdminPolicyExecutionListResponse(
        items=[
            AdminPolicyExecutionOut(
                id=str(item.id),
                policy_id=str(item.policy_id),
                event_type=item.event_type,
                event_id=str(item.event_id),
                action=item.action,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                reason=item.reason,
                created_at=item.created_at,
            )
            for item in executions
        ]
    )


@router.post("/{policy_type}/{policy_id}/enable", response_model=AdminPolicyHeader)
def enable_policy(
    policy_type: PolicyType = Path(..., alias="policy_type"),
    policy_id: str = Path(..., alias="policy_id"),
    db: Session = Depends(get_db),
) -> AdminPolicyHeader:
    if policy_type == PolicyType.FLEET:
        policy = db.query(FleetActionPolicy).filter(FleetActionPolicy.id == policy_id).one_or_none()
        if not policy:
            raise HTTPException(status_code=404, detail="policy_not_found")
        policy.active = True
        db.commit()
        db.refresh(policy)
        return AdminPolicyHeader(
            id=str(policy.id),
            type=PolicyType.FLEET,
            title=_fleet_policy_title(policy),
            status=_policy_status(policy.active),
            scope=PolicyScope(tenant_id=None, client_id=policy.client_id),
            actions=_fleet_policy_actions(policy),
            updated_at=policy.created_at,
            toggle_supported=True,
        )

    if policy_type == PolicyType.FINANCE:
        policy = db.query(RiskPolicy).filter(RiskPolicy.id == policy_id).one_or_none()
        if not policy:
            raise HTTPException(status_code=404, detail="policy_not_found")
        policy.active = True
        db.commit()
        db.refresh(policy)
        return AdminPolicyHeader(
            id=str(policy.id),
            type=PolicyType.FINANCE,
            title=_risk_policy_title(policy),
            status=_policy_status(policy.active),
            scope=PolicyScope(tenant_id=policy.tenant_id, client_id=policy.client_id),
            actions=_risk_policy_actions(policy),
            updated_at=None,
            toggle_supported=True,
        )

    raise HTTPException(status_code=409, detail="policy_toggle_not_supported")


@router.post("/{policy_type}/{policy_id}/disable", response_model=AdminPolicyHeader)
def disable_policy(
    policy_type: PolicyType = Path(..., alias="policy_type"),
    policy_id: str = Path(..., alias="policy_id"),
    db: Session = Depends(get_db),
) -> AdminPolicyHeader:
    if policy_type == PolicyType.FLEET:
        policy = db.query(FleetActionPolicy).filter(FleetActionPolicy.id == policy_id).one_or_none()
        if not policy:
            raise HTTPException(status_code=404, detail="policy_not_found")
        policy.active = False
        db.commit()
        db.refresh(policy)
        return AdminPolicyHeader(
            id=str(policy.id),
            type=PolicyType.FLEET,
            title=_fleet_policy_title(policy),
            status=_policy_status(policy.active),
            scope=PolicyScope(tenant_id=None, client_id=policy.client_id),
            actions=_fleet_policy_actions(policy),
            updated_at=policy.created_at,
            toggle_supported=True,
        )

    if policy_type == PolicyType.FINANCE:
        policy = db.query(RiskPolicy).filter(RiskPolicy.id == policy_id).one_or_none()
        if not policy:
            raise HTTPException(status_code=404, detail="policy_not_found")
        policy.active = False
        db.commit()
        db.refresh(policy)
        return AdminPolicyHeader(
            id=str(policy.id),
            type=PolicyType.FINANCE,
            title=_risk_policy_title(policy),
            status=_policy_status(policy.active),
            scope=PolicyScope(tenant_id=policy.tenant_id, client_id=policy.client_id),
            actions=_risk_policy_actions(policy),
            updated_at=None,
            toggle_supported=True,
        )

    raise HTTPException(status_code=409, detail="policy_toggle_not_supported")


__all__ = ["router"]
