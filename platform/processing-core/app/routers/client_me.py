from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.client import Client
from app.models.subscriptions_v1 import SubscriptionPlan
from app.schemas.client_me import (
    ClientMeEntitlements,
    ClientMeMembership,
    ClientMeOrg,
    ClientMeResponse,
    ClientMeSubscription,
    ClientMeUser,
)
from app.security.client_auth import require_onboarding_user
from app.services import entitlements_service
from app.services.client_entitlements import build_client_entitlements, normalize_roles
from app.services.subscription_service import (
    DEFAULT_TENANT_ID,
    compute_entitlements,
    ensure_free_subscription,
    get_client_subscription,
)

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
    if client is not None:
        org_payload = ClientMeOrg(
            id=str(client.id),
            name=client.name,
            inn=client.inn,
            status=str(client.status),
        )

    return ClientMeResponse(
        user=ClientMeUser(
            id=str(token.get("user_id") or token.get("sub") or ""),
            email=token.get("email") or token.get("sub"),
            subject_type=token.get("subject_type"),
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
