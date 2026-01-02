from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.cases import Case, CaseEventType, CaseKind, CasePriority, CaseStatus
from app.models.fleet import (
    ClientEmployee,
    EmployeeStatus,
    FuelCardGroupMember,
    FuelGroupAccess,
    FuelGroupRole,
)
from app.models.fuel import (
    FuelCard,
    FuelCardGroup,
    FuelCardGroupStatus,
    FuelCardStatus,
    FuelLimit,
    FuelLimitPeriod,
    FuelLimitScopeType,
    FuelLimitType,
    FuelNetwork,
    FuelStation,
    FuelTransaction,
    FuelTransactionStatus,
    FuelType,
)
from app.security.rbac.principal import Principal
from app.services.case_event_redaction import redact_deep
from app.services.case_events_service import CaseEventActor, emit_case_event
from app.services.case_export_service import create_export
from app.services.decision_memory.records import record_decision_memory
from app.services.export_storage import ExportStorage
from neft_shared.settings import get_settings

settings = get_settings()


class FleetServiceError(Exception):
    pass


@dataclass(frozen=True)
class SpendSummaryRow:
    key: str
    amount: Decimal


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_client_access(principal: Principal, client_id: str) -> None:
    if principal.is_admin:
        return
    if principal.client_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "client"},
        )
    if str(principal.client_id) != str(client_id):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "not_owner", "resource": "client"})


def _is_client_admin(principal: Principal) -> bool:
    return principal.is_admin or "client_admin" in principal.roles


def _principal_email(principal: Principal) -> str | None:
    email = principal.raw_claims.get("email") if isinstance(principal.raw_claims, dict) else None
    return str(email) if email else None


def _employee_for_principal(db: Session, *, principal: Principal, client_id: str) -> ClientEmployee | None:
    if principal.user_id:
        employee = (
            db.query(ClientEmployee)
            .filter(ClientEmployee.id == str(principal.user_id))
            .filter(ClientEmployee.client_id == client_id)
            .one_or_none()
        )
        if employee:
            return employee
    email = _principal_email(principal)
    if email:
        return (
            db.query(ClientEmployee)
            .filter(ClientEmployee.client_id == client_id)
            .filter(func.lower(ClientEmployee.email) == email.lower())
            .one_or_none()
        )
    return None


def _role_rank(role: FuelGroupRole) -> int:
    order = {
        FuelGroupRole.VIEWER: 1,
        FuelGroupRole.MANAGER: 2,
        FuelGroupRole.ADMIN: 3,
    }
    return order.get(role, 0)


def require_group_role(db: Session, *, principal: Principal, group_id: str, min_role: FuelGroupRole) -> None:
    group = db.query(FuelCardGroup).filter(FuelCardGroup.id == group_id).one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="group_not_found")
    if _is_client_admin(principal):
        return
    employee = _employee_for_principal(db, principal=principal, client_id=group.client_id)
    if not employee:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "missing_employee"})
    access = (
        db.query(FuelGroupAccess)
        .filter(FuelGroupAccess.group_id == group_id)
        .filter(FuelGroupAccess.employee_id == employee.id)
        .filter(FuelGroupAccess.revoked_at.is_(None))
        .one_or_none()
    )
    if not access or _role_rank(access.role) < _role_rank(min_role):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "insufficient_group_role"})


def _accessible_group_ids(db: Session, *, principal: Principal, client_id: str) -> list[str]:
    if _is_client_admin(principal):
        return [str(item.id) for item in db.query(FuelCardGroup.id).filter(FuelCardGroup.client_id == client_id).all()]
    employee = _employee_for_principal(db, principal=principal, client_id=client_id)
    if not employee:
        return []
    rows = (
        db.query(FuelGroupAccess.group_id)
        .filter(FuelGroupAccess.employee_id == employee.id)
        .filter(FuelGroupAccess.revoked_at.is_(None))
        .all()
    )
    return [str(row[0]) for row in rows]


def _accessible_card_ids(db: Session, *, principal: Principal, client_id: str) -> list[str]:
    if _is_client_admin(principal):
        rows = db.query(FuelCard.id).filter(FuelCard.client_id == client_id).all()
        return [str(row[0]) for row in rows]
    group_ids = _accessible_group_ids(db, principal=principal, client_id=client_id)
    if not group_ids:
        return []
    rows = (
        db.query(FuelCardGroupMember.card_id)
        .filter(FuelCardGroupMember.group_id.in_(group_ids))
        .filter(FuelCardGroupMember.removed_at.is_(None))
        .all()
    )
    return [str(row[0]) for row in rows]


def _ensure_card_access(db: Session, *, principal: Principal, card: FuelCard) -> None:
    _ensure_client_access(principal, card.client_id)
    if _is_client_admin(principal):
        return
    card_ids = _accessible_card_ids(db, principal=principal, client_id=card.client_id)
    if str(card.id) not in card_ids:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "no_card_access"})


def _ensure_card_manager_access(db: Session, *, principal: Principal, card: FuelCard) -> None:
    _ensure_client_access(principal, card.client_id)
    if _is_client_admin(principal):
        return
    employee = _employee_for_principal(db, principal=principal, client_id=card.client_id)
    if not employee:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "missing_employee"})
    group_ids = (
        db.query(FuelCardGroupMember.group_id)
        .filter(FuelCardGroupMember.card_id == card.id)
        .filter(FuelCardGroupMember.removed_at.is_(None))
        .all()
    )
    if not group_ids:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "card_not_in_group"})
    access = (
        db.query(FuelGroupAccess)
        .filter(FuelGroupAccess.employee_id == employee.id)
        .filter(FuelGroupAccess.group_id.in_([row[0] for row in group_ids]))
        .filter(FuelGroupAccess.revoked_at.is_(None))
        .all()
    )
    if not any(_role_rank(item.role) >= _role_rank(FuelGroupRole.MANAGER) for item in access):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "insufficient_group_role"})


def _case_actor(principal: Principal | None) -> CaseEventActor | None:
    if not principal:
        return None
    actor_id = str(principal.user_id) if principal.user_id else None
    return CaseEventActor(id=actor_id, email=_principal_email(principal))


def _resolve_tenant_id(principal: Principal | None) -> int:
    if principal and isinstance(principal.raw_claims, dict):
        tenant_id = principal.raw_claims.get("tenant_id")
        if isinstance(tenant_id, int):
            return tenant_id
        if isinstance(tenant_id, str) and tenant_id.isdigit():
            return int(tenant_id)
    return 0


def _get_or_create_fleet_case(
    db: Session,
    *,
    client_id: str,
    tenant_id: int,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> Case:
    case = (
        db.query(Case)
        .filter(Case.kind == CaseKind.FLEET)
        .filter(Case.entity_id == client_id)
        .one_or_none()
    )
    if case:
        return case
    case = Case(
        tenant_id=tenant_id,
        kind=CaseKind.FLEET,
        entity_id=client_id,
        title=f"Fleet client {client_id}",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        created_by=str(principal.user_id) if principal and principal.user_id else None,
        updated_at=_now(),
        last_activity_at=_now(),
    )
    db.add(case)
    db.flush()
    emit_case_event(
        db,
        case_id=str(case.id),
        event_type=CaseEventType.CASE_CREATED,
        actor=_case_actor(principal),
        request_id=request_id,
        trace_id=trace_id,
        changes=None,
        extra_payload={"entity_id": client_id, "kind": CaseKind.FLEET.value},
    )
    db.flush()
    return case


def _emit_event(
    db: Session,
    *,
    client_id: str,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
    event_type: CaseEventType,
    payload: dict[str, Any],
) -> str:
    case = _get_or_create_fleet_case(
        db,
        client_id=client_id,
        tenant_id=_resolve_tenant_id(principal),
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    event = emit_case_event(
        db,
        case_id=str(case.id),
        event_type=event_type,
        actor=_case_actor(principal),
        request_id=request_id,
        trace_id=trace_id,
        changes=None,
        extra_payload=payload,
    )
    return str(event.id)


def list_cards(db: Session, *, client_id: str, principal: Principal) -> list[FuelCard]:
    _ensure_client_access(principal, client_id)
    if _is_client_admin(principal):
        return db.query(FuelCard).filter(FuelCard.client_id == client_id).order_by(FuelCard.created_at.desc()).all()
    card_ids = _accessible_card_ids(db, principal=principal, client_id=client_id)
    if not card_ids:
        return []
    return db.query(FuelCard).filter(FuelCard.id.in_(card_ids)).order_by(FuelCard.created_at.desc()).all()


def create_card(
    db: Session,
    *,
    client_id: str,
    alias: str,
    masked_pan: str,
    token_ref: str | None,
    currency: str | None,
    issued_at: datetime | None,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> FuelCard:
    _ensure_client_access(principal, client_id)
    tenant_id = _resolve_tenant_id(principal)
    card = FuelCard(
        tenant_id=tenant_id,
        client_id=client_id,
        card_token=token_ref or alias,
        card_alias=alias,
        masked_pan=masked_pan,
        token_ref=token_ref,
        status=FuelCardStatus.ACTIVE,
        currency=currency or "RUB",
        issued_at=issued_at,
    )
    db.add(card)
    db.flush()
    audit_event_id = _emit_event(
        db,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.CARD_CREATED,
        payload={
            "card_id": str(card.id),
            "card_alias": alias,
            "masked_pan": masked_pan,
            "status": FuelCardStatus.ACTIVE.value,
        },
    )
    card.audit_event_id = audit_event_id
    return card


def get_card(db: Session, *, card_id: str, principal: Principal) -> FuelCard:
    card = db.query(FuelCard).filter(FuelCard.id == card_id).one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="card_not_found")
    _ensure_card_access(db, principal=principal, card=card)
    return card


def set_card_status(
    db: Session,
    *,
    card_id: str,
    status: FuelCardStatus,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> FuelCard:
    card = get_card(db, card_id=card_id, principal=principal)
    if not _is_client_admin(principal):
        _ensure_card_manager_access(db, principal=principal, card=card)
    previous = card.status
    card.status = status
    audit_event_id = _emit_event(
        db,
        client_id=card.client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.CARD_STATUS_CHANGED,
        payload={
            "card_id": str(card.id),
            "previous_status": previous.value if previous else None,
            "new_status": status.value,
        },
    )
    card.audit_event_id = audit_event_id
    record_decision_memory(
        db,
        case_id=None,
        decision_type="card_status",
        decision_ref_id=str(card.id),
        decision_at=_now(),
        decided_by_user_id=str(principal.user_id) if principal.user_id else None,
        context_snapshot={"card_id": str(card.id), "status": status.value},
        rationale="card_status_change",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=audit_event_id,
    )
    return card


def list_groups(db: Session, *, client_id: str, principal: Principal) -> list[FuelCardGroup]:
    _ensure_client_access(principal, client_id)
    if _is_client_admin(principal):
        return db.query(FuelCardGroup).filter(FuelCardGroup.client_id == client_id).order_by(
            FuelCardGroup.created_at.desc()
        ).all()
    group_ids = _accessible_group_ids(db, principal=principal, client_id=client_id)
    if not group_ids:
        return []
    return db.query(FuelCardGroup).filter(FuelCardGroup.id.in_(group_ids)).order_by(
        FuelCardGroup.created_at.desc()
    ).all()


def create_group(
    db: Session,
    *,
    client_id: str,
    name: str,
    description: str | None,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> FuelCardGroup:
    _ensure_client_access(principal, client_id)
    if not _is_client_admin(principal):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "client_admin_required"})
    group = FuelCardGroup(
        tenant_id=_resolve_tenant_id(principal),
        client_id=client_id,
        name=name,
        description=description,
        status=FuelCardGroupStatus.ACTIVE,
    )
    db.add(group)
    db.flush()
    audit_event_id = _emit_event(
        db,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.GROUP_CREATED,
        payload={"group_id": str(group.id), "name": name},
    )
    group.audit_event_id = audit_event_id
    return group


def add_card_to_group(
    db: Session,
    *,
    group_id: str,
    card_id: str,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> FuelCardGroupMember:
    require_group_role(db, principal=principal, group_id=group_id, min_role=FuelGroupRole.ADMIN)
    member = (
        db.query(FuelCardGroupMember)
        .filter(FuelCardGroupMember.group_id == group_id)
        .filter(FuelCardGroupMember.card_id == card_id)
        .one_or_none()
    )
    group_client_id = db.query(FuelCardGroup.client_id).filter(FuelCardGroup.id == group_id).scalar()
    if member:
        member.removed_at = None
    else:
        member = FuelCardGroupMember(group_id=group_id, card_id=card_id)
        db.add(member)
    audit_event_id = _emit_event(
        db,
        client_id=group_client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.GROUP_MEMBER_ADDED,
        payload={"group_id": group_id, "card_id": card_id},
    )
    member.audit_event_id = audit_event_id
    db.flush()
    return member


def remove_card_from_group(
    db: Session,
    *,
    group_id: str,
    card_id: str,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> FuelCardGroupMember:
    require_group_role(db, principal=principal, group_id=group_id, min_role=FuelGroupRole.ADMIN)
    member = (
        db.query(FuelCardGroupMember)
        .filter(FuelCardGroupMember.group_id == group_id)
        .filter(FuelCardGroupMember.card_id == card_id)
        .one_or_none()
    )
    if not member:
        raise HTTPException(status_code=404, detail="group_member_not_found")
    member.removed_at = _now()
    group_client_id = db.query(FuelCardGroup.client_id).filter(FuelCardGroup.id == group_id).scalar()
    audit_event_id = _emit_event(
        db,
        client_id=group_client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.GROUP_MEMBER_REMOVED,
        payload={"group_id": group_id, "card_id": card_id},
    )
    member.audit_event_id = audit_event_id
    db.flush()
    return member


def list_employees(db: Session, *, client_id: str, principal: Principal) -> list[ClientEmployee]:
    _ensure_client_access(principal, client_id)
    if not _is_client_admin(principal):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "client_admin_required"})
    return (
        db.query(ClientEmployee)
        .filter(ClientEmployee.client_id == client_id)
        .order_by(ClientEmployee.created_at.desc())
        .all()
    )


def invite_employee(
    db: Session,
    *,
    client_id: str,
    email: str,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> ClientEmployee:
    _ensure_client_access(principal, client_id)
    if not _is_client_admin(principal):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "client_admin_required"})
    employee = ClientEmployee(client_id=client_id, email=email, status=EmployeeStatus.INVITED)
    db.add(employee)
    db.flush()
    audit_event_id = _emit_event(
        db,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.GROUP_ACCESS_GRANTED,
        payload={"employee_id": str(employee.id), "email": email, "status": EmployeeStatus.INVITED.value},
    )
    employee.audit_event_id = audit_event_id
    return employee


def disable_employee(
    db: Session,
    *,
    employee_id: str,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> ClientEmployee:
    employee = db.query(ClientEmployee).filter(ClientEmployee.id == employee_id).one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="employee_not_found")
    _ensure_client_access(principal, employee.client_id)
    if not _is_client_admin(principal):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "client_admin_required"})
    employee.status = EmployeeStatus.DISABLED
    audit_event_id = _emit_event(
        db,
        client_id=employee.client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.GROUP_ACCESS_REVOKED,
        payload={"employee_id": str(employee.id), "status": EmployeeStatus.DISABLED.value},
    )
    employee.audit_event_id = audit_event_id
    return employee


def list_group_access(db: Session, *, group_id: str, principal: Principal) -> list[FuelGroupAccess]:
    require_group_role(db, principal=principal, group_id=group_id, min_role=FuelGroupRole.ADMIN)
    return (
        db.query(FuelGroupAccess)
        .filter(FuelGroupAccess.group_id == group_id)
        .order_by(FuelGroupAccess.created_at.desc())
        .all()
    )


def grant_group_access(
    db: Session,
    *,
    group_id: str,
    employee_id: str,
    role: FuelGroupRole,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> FuelGroupAccess:
    require_group_role(db, principal=principal, group_id=group_id, min_role=FuelGroupRole.ADMIN)
    access = (
        db.query(FuelGroupAccess)
        .filter(FuelGroupAccess.group_id == group_id)
        .filter(FuelGroupAccess.employee_id == employee_id)
        .one_or_none()
    )
    if access:
        access.role = role
        access.revoked_at = None
    else:
        group_client_id = db.query(FuelCardGroup.client_id).filter(FuelCardGroup.id == group_id).scalar()
        access = FuelGroupAccess(
            client_id=group_client_id,
            group_id=group_id,
            employee_id=employee_id,
            role=role,
        )
        db.add(access)
    db.flush()
    audit_event_id = _emit_event(
        db,
        client_id=db.query(FuelCardGroup.client_id).filter(FuelCardGroup.id == group_id).scalar(),
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.GROUP_ACCESS_GRANTED,
        payload={"group_id": group_id, "employee_id": employee_id, "role": role.value},
    )
    access.audit_event_id = audit_event_id
    record_decision_memory(
        db,
        case_id=None,
        decision_type="group_access",
        decision_ref_id=str(access.id),
        decision_at=_now(),
        decided_by_user_id=str(principal.user_id) if principal.user_id else None,
        context_snapshot={"group_id": group_id, "employee_id": employee_id, "role": role.value},
        rationale="group_access_grant",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=audit_event_id,
    )
    return access


def revoke_group_access(
    db: Session,
    *,
    group_id: str,
    employee_id: str,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> FuelGroupAccess:
    require_group_role(db, principal=principal, group_id=group_id, min_role=FuelGroupRole.ADMIN)
    access = (
        db.query(FuelGroupAccess)
        .filter(FuelGroupAccess.group_id == group_id)
        .filter(FuelGroupAccess.employee_id == employee_id)
        .one_or_none()
    )
    if not access:
        raise HTTPException(status_code=404, detail="access_not_found")
    access.revoked_at = _now()
    audit_event_id = _emit_event(
        db,
        client_id=db.query(FuelCardGroup.client_id).filter(FuelCardGroup.id == group_id).scalar(),
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.GROUP_ACCESS_REVOKED,
        payload={"group_id": group_id, "employee_id": employee_id},
    )
    access.audit_event_id = audit_event_id
    record_decision_memory(
        db,
        case_id=None,
        decision_type="group_access",
        decision_ref_id=str(access.id),
        decision_at=_now(),
        decided_by_user_id=str(principal.user_id) if principal.user_id else None,
        context_snapshot={"group_id": group_id, "employee_id": employee_id, "revoked": True},
        rationale="group_access_revoke",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=audit_event_id,
    )
    return access


def list_limits(
    db: Session,
    *,
    client_id: str,
    scope_type: FuelLimitScopeType,
    scope_id: str,
    principal: Principal,
) -> list[FuelLimit]:
    _ensure_client_access(principal, client_id)
    if scope_type == FuelLimitScopeType.CARD_GROUP:
        require_group_role(db, principal=principal, group_id=scope_id, min_role=FuelGroupRole.VIEWER)
    elif scope_type == FuelLimitScopeType.CARD:
        card = db.query(FuelCard).filter(FuelCard.id == scope_id).one_or_none()
        if not card:
            raise HTTPException(status_code=404, detail="card_not_found")
        _ensure_card_access(db, principal=principal, card=card)
    return (
        db.query(FuelLimit)
        .filter(FuelLimit.client_id == client_id)
        .filter(FuelLimit.scope_type == scope_type)
        .filter(FuelLimit.scope_id == scope_id)
        .order_by(FuelLimit.created_at.desc())
        .all()
    )


def set_limit(
    db: Session,
    *,
    client_id: str,
    scope_type: FuelLimitScopeType,
    scope_id: str,
    period: FuelLimitPeriod,
    amount_limit: Decimal | None,
    volume_limit_liters: Decimal | None,
    categories: dict[str, Any] | None,
    stations_allowlist: dict[str, Any] | None,
    effective_from: datetime | None,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> FuelLimit:
    _ensure_client_access(principal, client_id)
    if scope_type == FuelLimitScopeType.CARD_GROUP:
        require_group_role(db, principal=principal, group_id=scope_id, min_role=FuelGroupRole.MANAGER)
    elif scope_type == FuelLimitScopeType.CARD:
        card = db.query(FuelCard).filter(FuelCard.id == scope_id).one_or_none()
        if not card:
            raise HTTPException(status_code=404, detail="card_not_found")
        _ensure_card_manager_access(db, principal=principal, card=card)
    limit_type = FuelLimitType.AMOUNT
    value = 0
    if amount_limit is not None:
        limit_type = FuelLimitType.AMOUNT
        value = int((amount_limit * Decimal("100")).quantize(Decimal("1")))
    elif volume_limit_liters is not None:
        limit_type = FuelLimitType.VOLUME
        value = int((volume_limit_liters * Decimal("1000")).quantize(Decimal("1")))
    limit = FuelLimit(
        tenant_id=_resolve_tenant_id(principal),
        client_id=client_id,
        scope_type=scope_type,
        scope_id=scope_id,
        limit_type=limit_type,
        period=period,
        value=value,
        amount_limit=amount_limit,
        volume_limit_liters=volume_limit_liters,
        categories=categories,
        stations_allowlist=stations_allowlist,
        effective_from=effective_from,
        active=True,
    )
    db.add(limit)
    db.flush()
    audit_event_id = _emit_event(
        db,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.LIMIT_SET,
        payload={
            "limit_id": str(limit.id),
            "scope_type": scope_type.value,
            "scope_id": scope_id,
            "amount_limit": str(amount_limit) if amount_limit is not None else None,
            "volume_limit_liters": str(volume_limit_liters) if volume_limit_liters is not None else None,
            "period": period.value,
        },
    )
    limit.audit_event_id = audit_event_id
    record_decision_memory(
        db,
        case_id=None,
        decision_type="limit",
        decision_ref_id=str(limit.id),
        decision_at=_now(),
        decided_by_user_id=str(principal.user_id) if principal.user_id else None,
        context_snapshot={
            "scope_type": scope_type.value,
            "scope_id": scope_id,
            "amount_limit": str(amount_limit) if amount_limit is not None else None,
            "volume_limit_liters": str(volume_limit_liters) if volume_limit_liters is not None else None,
            "period": period.value,
        },
        rationale="limit_set",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=audit_event_id,
    )
    return limit


def revoke_limit(
    db: Session,
    *,
    limit_id: str,
    principal: Principal,
    request_id: str | None,
    trace_id: str | None,
) -> FuelLimit:
    limit = db.query(FuelLimit).filter(FuelLimit.id == limit_id).one_or_none()
    if not limit:
        raise HTTPException(status_code=404, detail="limit_not_found")
    _ensure_client_access(principal, limit.client_id)
    if limit.scope_type == FuelLimitScopeType.CARD_GROUP:
        require_group_role(db, principal=principal, group_id=str(limit.scope_id), min_role=FuelGroupRole.MANAGER)
    elif limit.scope_type == FuelLimitScopeType.CARD:
        card = db.query(FuelCard).filter(FuelCard.id == limit.scope_id).one_or_none()
        if not card:
            raise HTTPException(status_code=404, detail="card_not_found")
        _ensure_card_manager_access(db, principal=principal, card=card)
    limit.active = False
    audit_event_id = _emit_event(
        db,
        client_id=limit.client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.LIMIT_REVOKED,
        payload={"limit_id": str(limit.id), "scope_id": str(limit.scope_id)},
    )
    limit.audit_event_id = audit_event_id
    record_decision_memory(
        db,
        case_id=None,
        decision_type="limit",
        decision_ref_id=str(limit.id),
        decision_at=_now(),
        decided_by_user_id=str(principal.user_id) if principal.user_id else None,
        context_snapshot={"limit_id": str(limit.id), "active": False},
        rationale="limit_revoke",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=audit_event_id,
    )
    return limit


def _ensure_network_station(db: Session, *, station_external_id: str | None) -> tuple[FuelNetwork, FuelStation]:
    network = (
        db.query(FuelNetwork)
        .filter(FuelNetwork.provider_code == "FLEET")
        .one_or_none()
    )
    if not network:
        network = FuelNetwork(name="Fleet", provider_code="FLEET", status="ACTIVE")
        db.add(network)
        db.flush()
    station = None
    if station_external_id:
        station = (
            db.query(FuelStation)
            .filter(FuelStation.network_id == network.id)
            .filter(FuelStation.station_code == station_external_id)
            .one_or_none()
        )
    if not station:
        station = FuelStation(
            network_id=network.id,
            name=station_external_id or "Fleet station",
            station_code=station_external_id,
            status="ACTIVE",
        )
        db.add(station)
        db.flush()
    return network, station


def ingest_transactions(
    db: Session,
    *,
    client_id: str,
    items: Iterable[dict[str, Any]],
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> list[FuelTransaction]:
    tenant_id = _resolve_tenant_id(principal)
    created: list[FuelTransaction] = []
    payload_items = list(items)
    audit_event_id = _emit_event(
        db,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.TRANSACTION_INGESTED,
        payload={"count": len(payload_items)},
    )
    for payload in payload_items:
        external_ref = payload.get("external_ref")
        if external_ref:
            exists = (
                db.query(FuelTransaction)
                .filter(FuelTransaction.external_ref == external_ref)
                .one_or_none()
            )
            if exists:
                continue
        card_id = payload.get("card_id")
        if not card_id:
            raise FleetServiceError("card_id_required")
        card = db.query(FuelCard).filter(FuelCard.id == card_id).one_or_none()
        if not card:
            raise FleetServiceError("card_not_found")
        network, station = _ensure_network_station(db, station_external_id=payload.get("station_id"))
        amount = Decimal(str(payload.get("amount")))
        volume_liters = payload.get("volume_liters")
        volume_liters = Decimal(str(volume_liters)) if volume_liters is not None else None
        amount_minor = int((amount * Decimal("100")).quantize(Decimal("1")))
        volume_ml = int((volume_liters * Decimal("1000")).quantize(Decimal("1"))) if volume_liters else 0
        tx = FuelTransaction(
            tenant_id=tenant_id,
            client_id=client_id,
            card_id=card_id,
            station_id=station.id,
            network_id=network.id,
            occurred_at=payload.get("occurred_at") or _now(),
            fuel_type=FuelType.OTHER,
            volume_ml=volume_ml,
            unit_price_minor=0,
            amount_total_minor=amount_minor,
            currency=payload.get("currency") or "RUB",
            status=FuelTransactionStatus.SETTLED,
            external_ref=external_ref,
            amount=amount,
            volume_liters=volume_liters,
            category=payload.get("category"),
            merchant_name=payload.get("merchant_name"),
            station_external_id=payload.get("station_id"),
            location=payload.get("location"),
            raw_payload_redacted=redact_deep(payload.get("raw_payload"), "", include_hash=True)
            if payload.get("raw_payload")
            else None,
            audit_event_id=audit_event_id,
        )
        db.add(tx)
        created.append(tx)
    db.flush()
    return created


def list_transactions(
    db: Session,
    *,
    client_id: str,
    principal: Principal,
    card_id: str | None = None,
    group_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FuelTransaction]:
    _ensure_client_access(principal, client_id)
    query = db.query(FuelTransaction).filter(FuelTransaction.client_id == client_id)
    if card_id:
        card = db.query(FuelCard).filter(FuelCard.id == card_id).one_or_none()
        if not card:
            raise HTTPException(status_code=404, detail="card_not_found")
        _ensure_card_access(db, principal=principal, card=card)
        query = query.filter(FuelTransaction.card_id == card_id)
    if group_id:
        require_group_role(db, principal=principal, group_id=group_id, min_role=FuelGroupRole.VIEWER)
        card_ids = (
            db.query(FuelCardGroupMember.card_id)
            .filter(FuelCardGroupMember.group_id == group_id)
            .filter(FuelCardGroupMember.removed_at.is_(None))
            .all()
        )
        query = query.filter(FuelTransaction.card_id.in_([row[0] for row in card_ids]))
    if not card_id and not group_id and not _is_client_admin(principal):
        accessible_ids = _accessible_card_ids(db, principal=principal, client_id=client_id)
        if not accessible_ids:
            return []
        query = query.filter(FuelTransaction.card_id.in_(accessible_ids))
    if date_from:
        query = query.filter(FuelTransaction.occurred_at >= date_from)
    if date_to:
        query = query.filter(FuelTransaction.occurred_at <= date_to)
    return (
        query.order_by(FuelTransaction.occurred_at.desc(), FuelTransaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def spend_summary(
    db: Session,
    *,
    client_id: str,
    principal: Principal,
    group_by: str,
    card_id: str | None,
    group_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[SpendSummaryRow]:
    _ensure_client_access(principal, client_id)
    query = db.query(FuelTransaction).filter(FuelTransaction.client_id == client_id)
    if card_id:
        card = db.query(FuelCard).filter(FuelCard.id == card_id).one_or_none()
        if not card:
            raise HTTPException(status_code=404, detail="card_not_found")
        _ensure_card_access(db, principal=principal, card=card)
        query = query.filter(FuelTransaction.card_id == card_id)
    if group_id:
        require_group_role(db, principal=principal, group_id=group_id, min_role=FuelGroupRole.VIEWER)
        card_ids = (
            db.query(FuelCardGroupMember.card_id)
            .filter(FuelCardGroupMember.group_id == group_id)
            .filter(FuelCardGroupMember.removed_at.is_(None))
            .all()
        )
        query = query.filter(FuelTransaction.card_id.in_([row[0] for row in card_ids]))
    if date_from:
        query = query.filter(FuelTransaction.occurred_at >= date_from)
    if date_to:
        query = query.filter(FuelTransaction.occurred_at <= date_to)
    if group_by == "category":
        group_expr = FuelTransaction.category
    elif group_by == "card":
        group_expr = FuelTransaction.card_id
    else:
        group_expr = func.date(FuelTransaction.occurred_at)
    rows = (
        query.with_entities(group_expr, func.coalesce(func.sum(FuelTransaction.amount), 0))
        .group_by(group_expr)
        .order_by(group_expr)
        .all()
    )
    return [
        SpendSummaryRow(
            key=str(key),
            amount=Decimal(str(amount)).quantize(Decimal("0.01")),
        )
        for key, amount in rows
    ]


def export_transactions(
    db: Session,
    *,
    client_id: str,
    principal: Principal,
    card_id: str | None,
    group_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> tuple[str, str, int]:
    transactions = list_transactions(
        db,
        client_id=client_id,
        principal=principal,
        card_id=card_id,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
        limit=5000,
        offset=0,
    )
    payload = {
        "client_id": client_id,
        "transactions": [
            {
                "id": str(tx.id),
                "card_id": str(tx.card_id),
                "occurred_at": tx.occurred_at.isoformat() if tx.occurred_at else None,
                "amount": str(tx.amount) if tx.amount is not None else None,
                "currency": tx.currency,
                "volume_liters": str(tx.volume_liters) if tx.volume_liters is not None else None,
                "category": tx.category,
                "merchant_name": tx.merchant_name,
                "station_id": tx.station_external_id,
                "location": tx.location,
                "external_ref": tx.external_ref,
            }
            for tx in transactions
        ],
    }
    case = _get_or_create_fleet_case(
        db,
        client_id=client_id,
        tenant_id=_resolve_tenant_id(principal),
        principal=principal,
        request_id=None,
        trace_id=None,
    )
    export = create_export(
        db,
        kind="CASE",
        case_id=UUID(case.id),
        payload=payload,
        mastery_snapshot=None,
        actor=_case_actor(principal),
        request_id=None,
        trace_id=None,
    )
    storage = ExportStorage()
    url = storage.presign_get(export.object_key, ttl_seconds=settings.S3_SIGNED_URL_TTL_SECONDS)
    return str(export.id), url, settings.S3_SIGNED_URL_TTL_SECONDS


__all__ = [
    "SpendSummaryRow",
    "add_card_to_group",
    "create_card",
    "create_group",
    "disable_employee",
    "export_transactions",
    "get_card",
    "grant_group_access",
    "ingest_transactions",
    "list_cards",
    "list_employees",
    "list_group_access",
    "list_groups",
    "list_limits",
    "list_transactions",
    "remove_card_from_group",
    "revoke_group_access",
    "revoke_limit",
    "set_card_status",
    "set_limit",
    "spend_summary",
    "invite_employee",
    "require_group_role",
]
