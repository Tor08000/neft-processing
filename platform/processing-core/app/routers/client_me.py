from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fleet import ClientEmployee
from app.schemas.client_me import ClientAccountTimezoneUpdate, ClientMeUser
from app.schemas.portal_me import PortalMeResponse
from app.security.client_auth import require_onboarding_user
from app.services.audit_service import AuditService, request_context_from_request
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.portal_me import build_portal_me
from app.services.timezones import validate_timezone_name

router = APIRouter(prefix="/client", tags=["client-me"])


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


@router.get("/me", response_model=PortalMeResponse)
def get_client_me(
    request: Request,
    token: dict = Depends(require_onboarding_user),
    db: Session = Depends(get_db),
) -> PortalMeResponse:
    request_id = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
    return build_portal_me(db, token=token, request_id=request_id)


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
