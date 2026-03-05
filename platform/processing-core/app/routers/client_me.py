from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
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


@router.get("/me", include_in_schema=False)
def get_client_me(request: Request) -> RedirectResponse:
    target_path = request.url.path.replace("/client/me", "/portal/me")
    if target_path == request.url.path:
        target_path = "/api/core/portal/me"
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(url=f"{target_path}{query}", status_code=308)


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
