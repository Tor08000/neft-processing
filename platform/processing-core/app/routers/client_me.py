from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.client import Client
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
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.client_entitlements import build_client_entitlements, normalize_roles
from app.services.subscription_service import (
    DEFAULT_TENANT_ID,
    compute_entitlements,
    ensure_free_subscription,
    get_client_subscription,
)
from app.services.timezones import validate_timezone_name
from app.services.portal_me import build_portal_me

router = APIRouter(prefix="/client", tags=["client-me"])


def _resolve_org_status(client: Client | None) -> str:
    if client is None:
        return "NONE"
    return str(client.status or "UNKNOWN").upper()


def _resolve_org_id(token: dict) -> int | None:
    raw = token.get("org_id")
    if raw:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    raw = token.get("client_id")
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@router.get("/me", response_model=ClientMeResponse)
def get_client_me(
    token: dict = Depends(require_onboarding_user),
    db: Session = Depends(get_db),
) -> ClientMeResponse:
    portal_payload = build_portal_me(db, token=token)
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
    entitlements_snapshot = None
    entitlements_hash = None
    entitlements_computed_at = None

    org_id = _resolve_org_id(token)

    if client_id and client is not None:
        entitlements = entitlements_service.get_entitlements(db, client_id=str(client_id))
        if org_id is not None:
            entitlements_snapshot = get_org_entitlements_snapshot(db, org_id=org_id)
            entitlements_hash = entitlements_snapshot.hash
            entitlements_computed_at = entitlements_snapshot.computed_at
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
            snapshot_subscription = (
                entitlements_snapshot.entitlements.get("subscription") if entitlements_snapshot else None
            )
            subscription_payload = ClientMeSubscription(
                plan_code=plan.code if plan else entitlements.plan_code,
                status=str(subscription.status) if subscription else None,
                billing_cycle=snapshot_subscription.get("billing_cycle") if snapshot_subscription else None,
                support_plan=snapshot_subscription.get("support_plan") if snapshot_subscription else None,
                slo_tier=snapshot_subscription.get("slo_tier") if snapshot_subscription else None,
                addons=snapshot_subscription.get("addons") if snapshot_subscription else None,
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
    if portal_payload.org is not None:
        org_payload = ClientMeOrg(
            id=portal_payload.org.id,
            name=portal_payload.org.name,
            inn=portal_payload.org.inn,
            status=portal_payload.org.status or "UNKNOWN",
            timezone=portal_payload.org.timezone,
        )

    employee_timezone = portal_payload.user.timezone

    return ClientMeResponse(
        user=ClientMeUser(
            id=portal_payload.user.id,
            email=portal_payload.user.email,
            subject_type=portal_payload.user.subject_type,
            timezone=employee_timezone,
        ),
        org=org_payload,
        membership=ClientMeMembership(roles=normalized_roles, status="active"),
        subscription=subscription_payload,
        entitlements=ClientMeEntitlements(
            features=entitlements_snapshot.entitlements.get("features") if entitlements_snapshot else None,
            modules=entitlements_snapshot.entitlements.get("modules") if entitlements_snapshot else None,
            enabled_modules=entitlements_output.enabled_modules,
            permissions=entitlements_output.permissions,
            limits=entitlements_snapshot.entitlements.get("limits")
            if entitlements_snapshot
            else entitlements_output.limits,
            org_status=entitlements_output.org_status,
        ),
        entitlements_snapshot=entitlements_snapshot.entitlements if entitlements_snapshot else None,
        entitlements_hash=entitlements_hash,
        entitlements_computed_at=entitlements_computed_at,
        org_status=org_status,
    )


@router.get("/entitlements")
def get_client_entitlements(
    token: dict = Depends(require_onboarding_user),
    db: Session = Depends(get_db),
) -> dict:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")
    org_id = _resolve_org_id(token)
    if org_id is None:
        raise HTTPException(status_code=403, detail="missing_org_context")
    snapshot = get_org_entitlements_snapshot(db, org_id=org_id)
    return snapshot.entitlements


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
