from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.client import Client
from app.models.crm import CRMClient
from app.models.fleet import ClientEmployee
from app.models.subscriptions_v1 import SubscriptionPlan
from app.schemas.client_me import ClientAccountTimezoneUpdate
from app.schemas.client_me import (
    ClientMeEntitlements,
    ClientMeMembership,
    ClientMeOrg,
    ClientMeResponse,
    ClientMeSubscription,
    ClientMeUser,
)
from app.security.client_auth import require_onboarding_user
from app.services.audit_service import AuditService, request_context_from_request
from app.services import entitlements_service
from app.services.client_entitlements import build_client_entitlements, normalize_roles
from app.services.subscription_service import (
    DEFAULT_TENANT_ID,
    compute_entitlements,
    ensure_free_subscription,
    get_client_subscription,
)
from app.services.timezones import validate_timezone_name

router = APIRouter(prefix="/client", tags=["client-me"])


def _resolve_org_status(client: Client | None) -> str:
    if client is None:
        return "NONE"
    return str(client.status or "UNKNOWN").upper()


@router.get("/me", response_model=ClientMeResponse)
def get_client_me(
    token: dict = Depends(require_onboarding_user),
    db: Session = Depends(get_db),
) -> ClientMeResponse:
    client_id = token.get("client_id")
    client = db.get(Client, client_id) if client_id else None
    org_status = _resolve_org_status(client)
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if token.get("role"):
        roles.append(token["role"])
    normalized_roles = normalize_roles([str(role) for role in roles])

    subscription_payload = None
    entitlements_limits: dict[str, dict] = {}
    entitlements_modules: dict[str, dict] = {}
    role_entitlements: list[dict] = []

    if client_id and client is not None:
        entitlements = entitlements_service.get_entitlements(db, client_id=str(client_id))
        entitlements_limits = entitlements.limits
        entitlements_modules = entitlements.modules
        tenant_id = int(token.get("tenant_id") or DEFAULT_TENANT_ID)
        subscription = get_client_subscription(db, tenant_id=tenant_id, client_id=str(client_id))
        if subscription is None:
            subscription = ensure_free_subscription(db, tenant_id=tenant_id, client_id=str(client_id))
        if subscription:
            plan = db.get(SubscriptionPlan, subscription.plan_id)
            if plan:
                role_entitlements = [
                    compute_entitlements(db, plan_id=plan.id, role_code=role_code)
                    for role_code in normalized_roles
                ]
            subscription_payload = ClientMeSubscription(
                plan_code=plan.code if plan else entitlements.plan_code,
                status=str(subscription.status) if subscription else None,
                modules=entitlements.modules,
                limits=entitlements.limits,
            )

    entitlements_output = build_client_entitlements(
        roles=normalized_roles,
        org_status=org_status,
        modules=entitlements_modules,
        limits=entitlements_limits,
        role_entitlements=role_entitlements,
    )

    org_payload = None
    org_timezone = None
    crm_client = None
    if client is not None:
        crm_client = db.query(CRMClient).filter(CRMClient.id == str(client.id)).one_or_none()
        org_timezone = crm_client.timezone if crm_client else None
        org_payload = ClientMeOrg(
            id=str(client.id),
            name=client.name,
            inn=client.inn,
            status=str(client.status),
            timezone=org_timezone,
        )

    employee_timezone = None
    user_id = token.get("user_id") or token.get("sub")
    if user_id and client_id:
        employee = (
            db.query(ClientEmployee)
            .filter(ClientEmployee.id == str(user_id), ClientEmployee.client_id == str(client_id))
            .one_or_none()
        )
        employee_timezone = employee.timezone if employee else None

    return ClientMeResponse(
        user=ClientMeUser(
            id=str(token.get("user_id") or token.get("sub") or ""),
            email=token.get("email") or token.get("sub"),
            subject_type=token.get("subject_type"),
            timezone=employee_timezone,
        ),
        org=org_payload,
        membership=ClientMeMembership(roles=normalized_roles, status="active"),
        subscription=subscription_payload,
        entitlements=ClientMeEntitlements(
            enabled_modules=entitlements_output.enabled_modules,
            permissions=entitlements_output.permissions,
            limits=entitlements_output.limits,
            org_status=entitlements_output.org_status,
        ),
        org_status=org_status,
    )


@router.patch("/account", response_model=ClientMeUser)
def update_client_account_timezone(
    payload: ClientAccountTimezoneUpdate,
    request: Request,
    token: dict = Depends(require_onboarding_user),
    db: Session = Depends(get_db),
) -> ClientMeUser:
    user_id = token.get("user_id") or token.get("sub")
    client_id = token.get("client_id")
    if not user_id or not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")

    validate_timezone_name(payload.timezone)

    employee = (
        db.query(ClientEmployee)
        .filter(ClientEmployee.id == str(user_id), ClientEmployee.client_id == str(client_id))
        .one_or_none()
    )
    if not employee:
        raise HTTPException(status_code=404, detail="user_not_found")

    before = {"timezone": employee.timezone}
    employee.timezone = payload.timezone
    db.add(employee)
    db.flush()

    AuditService(db).audit(
        event_type="user_timezone_changed",
        entity_type="client_user",
        entity_id=str(employee.id),
        action="user_timezone_changed",
        before=before,
        after={"timezone": employee.timezone},
        request_ctx=request_context_from_request(request, token=token),
    )
    db.commit()

    return ClientMeUser(
        id=str(employee.id),
        email=token.get("email") or token.get("sub"),
        subject_type=token.get("subject_type"),
        timezone=employee.timezone,
    )
