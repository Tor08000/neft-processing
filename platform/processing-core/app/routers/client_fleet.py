from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fuel import FuelCardStatus, FuelLimitScopeType
from app.schemas.client_fleet import (
    FleetAccessGrantIn,
    FleetAccessListResponse,
    FleetAccessOut,
    FleetAccessRevokeIn,
    FleetCardCreateIn,
    FleetCardListResponse,
    FleetCardOut,
    FleetEmployeeInviteIn,
    FleetEmployeeListResponse,
    FleetEmployeeOut,
    FleetGroupCreateIn,
    FleetGroupListResponse,
    FleetGroupMemberChangeIn,
    FleetGroupOut,
    FleetLimitListResponse,
    FleetLimitOut,
    FleetLimitRevokeIn,
    FleetLimitSetIn,
    FleetSpendSummaryOut,
    FleetSpendSummaryRow,
    FleetTransactionListResponse,
    FleetTransactionOut,
    FleetTransactionsExportOut,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.permissions import Permission
from app.security.rbac.principal import Principal
from app.services import fleet_service

router = APIRouter(prefix="/api/client/fleet", tags=["client-fleet"])


def _request_ids(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("x-request-id"), request.headers.get("x-trace-id")


def _ensure_client_context(principal: Principal) -> str:
    if principal.client_id is None:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "missing_client"})
    return str(principal.client_id)


def _card_to_schema(card) -> FleetCardOut:
    return FleetCardOut(
        id=str(card.id),
        card_alias=card.card_alias,
        masked_pan=card.masked_pan,
        token_ref=card.token_ref,
        status=card.status,
        currency=card.currency,
        issued_at=card.issued_at,
        created_at=card.created_at,
    )


def _group_to_schema(group) -> FleetGroupOut:
    return FleetGroupOut(
        id=str(group.id),
        name=group.name,
        description=group.description,
        created_at=group.created_at,
    )


def _employee_to_schema(employee) -> FleetEmployeeOut:
    return FleetEmployeeOut(
        id=str(employee.id),
        email=employee.email,
        status=employee.status,
        created_at=employee.created_at,
    )


def _access_to_schema(access) -> FleetAccessOut:
    return FleetAccessOut(
        id=str(access.id),
        employee_id=str(access.employee_id),
        role=access.role,
        created_at=access.created_at,
        revoked_at=access.revoked_at,
    )


def _limit_to_schema(limit) -> FleetLimitOut:
    return FleetLimitOut(
        id=str(limit.id),
        scope_type=limit.scope_type,
        scope_id=str(limit.scope_id) if limit.scope_id else None,
        period=limit.period,
        amount_limit=limit.amount_limit,
        volume_limit_liters=limit.volume_limit_liters,
        categories=limit.categories,
        stations_allowlist=limit.stations_allowlist,
        active=limit.active,
        effective_from=limit.effective_from,
        created_at=limit.created_at,
    )


def _transaction_to_schema(tx) -> FleetTransactionOut:
    return FleetTransactionOut(
        id=str(tx.id),
        card_id=str(tx.card_id),
        occurred_at=tx.occurred_at,
        amount=tx.amount,
        currency=tx.currency,
        volume_liters=tx.volume_liters,
        category=tx.category,
        merchant_name=tx.merchant_name,
        station_id=tx.station_external_id,
        location=tx.location,
        external_ref=tx.external_ref,
        created_at=tx.created_at,
    )


@router.get(
    "/cards",
    response_model=FleetCardListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_CARDS_LIST.value))],
)
def list_cards(
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_CARDS_LIST.value)),
    db: Session = Depends(get_db),
) -> FleetCardListResponse:
    client_id = _ensure_client_context(principal)
    cards = fleet_service.list_cards(db, client_id=client_id, principal=principal)
    return FleetCardListResponse(items=[_card_to_schema(card) for card in cards])


@router.post(
    "/cards",
    response_model=FleetCardOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value))],
)
def create_card(
    payload: FleetCardCreateIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetCardOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    card = fleet_service.create_card(
        db,
        client_id=client_id,
        alias=payload.card_alias,
        masked_pan=payload.masked_pan,
        token_ref=payload.token_ref,
        currency=payload.currency,
        issued_at=payload.issued_at,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _card_to_schema(card)


@router.get(
    "/cards/{card_id}",
    response_model=FleetCardOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_CARDS_VIEW.value))],
)
def get_card(
    card_id: str,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_CARDS_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetCardOut:
    card = fleet_service.get_card(db, card_id=card_id, principal=principal)
    return _card_to_schema(card)


@router.post(
    "/cards/{card_id}/block",
    response_model=FleetCardOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value))],
)
def block_card(
    card_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetCardOut:
    request_id, trace_id = _request_ids(request)
    card = fleet_service.set_card_status(
        db,
        card_id=card_id,
        status=FuelCardStatus.BLOCKED,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _card_to_schema(card)


@router.post(
    "/cards/{card_id}/unblock",
    response_model=FleetCardOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value))],
)
def unblock_card(
    card_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetCardOut:
    request_id, trace_id = _request_ids(request)
    card = fleet_service.set_card_status(
        db,
        card_id=card_id,
        status=FuelCardStatus.ACTIVE,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _card_to_schema(card)


@router.get(
    "/groups",
    response_model=FleetGroupListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_LIST.value))],
)
def list_groups(
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_LIST.value)),
    db: Session = Depends(get_db),
) -> FleetGroupListResponse:
    client_id = _ensure_client_context(principal)
    groups = fleet_service.list_groups(db, client_id=client_id, principal=principal)
    return FleetGroupListResponse(items=[_group_to_schema(group) for group in groups])


@router.post(
    "/groups",
    response_model=FleetGroupOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def create_group(
    payload: FleetGroupCreateIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetGroupOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    group = fleet_service.create_group(
        db,
        client_id=client_id,
        name=payload.name,
        description=payload.description,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _group_to_schema(group)


@router.post(
    "/groups/{group_id}/members/add",
    response_model=dict,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def add_card_to_group(
    group_id: str,
    payload: FleetGroupMemberChangeIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> dict:
    request_id, trace_id = _request_ids(request)
    member = fleet_service.add_card_to_group(
        db,
        group_id=group_id,
        card_id=payload.card_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return {"group_id": str(member.group_id), "card_id": str(member.card_id)}


@router.post(
    "/groups/{group_id}/members/remove",
    response_model=dict,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def remove_card_from_group(
    group_id: str,
    payload: FleetGroupMemberChangeIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> dict:
    request_id, trace_id = _request_ids(request)
    member = fleet_service.remove_card_from_group(
        db,
        group_id=group_id,
        card_id=payload.card_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return {"group_id": str(member.group_id), "card_id": str(member.card_id)}


@router.get(
    "/groups/{group_id}/access",
    response_model=FleetAccessListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def list_group_access(
    group_id: str,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetAccessListResponse:
    items = fleet_service.list_group_access(db, group_id=group_id, principal=principal)
    return FleetAccessListResponse(items=[_access_to_schema(item) for item in items])


@router.post(
    "/groups/{group_id}/access/grant",
    response_model=FleetAccessOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def grant_group_access(
    group_id: str,
    payload: FleetAccessGrantIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetAccessOut:
    request_id, trace_id = _request_ids(request)
    access = fleet_service.grant_group_access(
        db,
        group_id=group_id,
        employee_id=payload.employee_id,
        role=payload.role,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _access_to_schema(access)


@router.post(
    "/groups/{group_id}/access/revoke",
    response_model=FleetAccessOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def revoke_group_access(
    group_id: str,
    payload: FleetAccessRevokeIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetAccessOut:
    request_id, trace_id = _request_ids(request)
    access = fleet_service.revoke_group_access(
        db,
        group_id=group_id,
        employee_id=payload.employee_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _access_to_schema(access)


@router.get(
    "/limits",
    response_model=FleetLimitListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def list_limits(
    scope_type: FuelLimitScopeType = Query(...),
    scope_id: str = Query(...),
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetLimitListResponse:
    client_id = _ensure_client_context(principal)
    limits = fleet_service.list_limits(
        db,
        client_id=client_id,
        scope_type=scope_type,
        scope_id=scope_id,
        principal=principal,
    )
    return FleetLimitListResponse(items=[_limit_to_schema(limit) for limit in limits])


@router.post(
    "/limits/set",
    response_model=FleetLimitOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_LIMITS_MANAGE.value))],
)
def set_limit(
    payload: FleetLimitSetIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_LIMITS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetLimitOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    limit = fleet_service.set_limit(
        db,
        client_id=client_id,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        period=payload.period,
        amount_limit=payload.amount_limit,
        volume_limit_liters=payload.volume_limit_liters,
        categories=payload.categories,
        stations_allowlist=payload.stations_allowlist,
        effective_from=payload.effective_from,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _limit_to_schema(limit)


@router.post(
    "/limits/revoke",
    response_model=FleetLimitOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_LIMITS_MANAGE.value))],
)
def revoke_limit(
    payload: FleetLimitRevokeIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_LIMITS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetLimitOut:
    request_id, trace_id = _request_ids(request)
    limit = fleet_service.revoke_limit(
        db,
        limit_id=payload.limit_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _limit_to_schema(limit)


@router.get(
    "/transactions",
    response_model=FleetTransactionListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def list_transactions(
    card_id: str | None = Query(None),
    group_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetTransactionListResponse:
    client_id = _ensure_client_context(principal)
    items = fleet_service.list_transactions(
        db,
        client_id=client_id,
        principal=principal,
        card_id=card_id,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return FleetTransactionListResponse(items=[_transaction_to_schema(item) for item in items])


@router.get(
    "/spend/summary",
    response_model=FleetSpendSummaryOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def spend_summary(
    group_by: str = Query("day"),
    card_id: str | None = Query(None),
    group_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetSpendSummaryOut:
    client_id = _ensure_client_context(principal)
    rows = fleet_service.spend_summary(
        db,
        client_id=client_id,
        principal=principal,
        group_by=group_by,
        card_id=card_id,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
    )
    return FleetSpendSummaryOut(
        group_by=group_by,
        rows=[FleetSpendSummaryRow(key=row.key, amount=row.amount) for row in rows],
    )


@router.get(
    "/transactions/export",
    response_model=FleetTransactionsExportOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def export_transactions(
    card_id: str | None = Query(None),
    group_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetTransactionsExportOut:
    client_id = _ensure_client_context(principal)
    export_id, url, expires_in = fleet_service.export_transactions(
        db,
        client_id=client_id,
        principal=principal,
        card_id=card_id,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
    )
    db.commit()
    return FleetTransactionsExportOut(export_id=export_id, url=url, expires_in=expires_in)


@router.get(
    "/employees",
    response_model=FleetEmployeeListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def list_employees(
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetEmployeeListResponse:
    client_id = _ensure_client_context(principal)
    employees = fleet_service.list_employees(db, client_id=client_id, principal=principal)
    return FleetEmployeeListResponse(items=[_employee_to_schema(item) for item in employees])


@router.post(
    "/employees/invite",
    response_model=FleetEmployeeOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def invite_employee(
    payload: FleetEmployeeInviteIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetEmployeeOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    employee = fleet_service.invite_employee(
        db,
        client_id=client_id,
        email=payload.email,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _employee_to_schema(employee)


@router.post(
    "/employees/{employee_id}/disable",
    response_model=FleetEmployeeOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def disable_employee(
    employee_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetEmployeeOut:
    request_id, trace_id = _request_ids(request)
    employee = fleet_service.disable_employee(
        db,
        employee_id=employee_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _employee_to_schema(employee)


__all__ = ["router"]
