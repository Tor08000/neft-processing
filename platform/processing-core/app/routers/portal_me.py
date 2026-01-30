from __future__ import annotations

import logging
from datetime import datetime, timezone

from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.security.rbac.principal import Principal, get_principal
from app.db import get_db
from app.schemas.portal_me import PortalAccessState, PortalMeFeatures, PortalMeGating, PortalMeResponse, PortalMeUser
from app.services.portal_me import build_portal_me

router = APIRouter(prefix="/portal", tags=["portal-me"])
logger = logging.getLogger(__name__)


@router.get("/me", response_model=PortalMeResponse)
def get_portal_me(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    request: Request = None,
) -> PortalMeResponse:
    try:
        return build_portal_me(db, token=principal.raw_claims)
    except Exception:
        logger.exception("portal_me_failed", extra={"actor": principal.raw_claims.get("sub")})
        token = principal.raw_claims or {}
        request_id = None
        if request is not None:
            request_id = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
        error_id = uuid4().hex
        return PortalMeResponse(
            actor_type="client",
            context="client",
            user=PortalMeUser(
                id=str(token.get("user_id") or token.get("sub") or ""),
                email=token.get("email") or token.get("sub"),
                subject_type=token.get("subject_type"),
                timezone="UTC",
            ),
            org=None,
            org_status=None,
            org_roles=[],
            user_roles=[],
            roles=[],
            memberships=[],
            scopes=None,
            flags={
                "portal_me_failed": True,
                "error_id": error_id,
                "request_id": request_id,
                "reason_code": "portal_me_failed",
            },
            legal=None,
            features=PortalMeFeatures(onboarding_enabled=True, legal_gate_enabled=True),
            gating=PortalMeGating(onboarding_enabled=True, legal_gate_enabled=True),
            subscription=None,
            entitlements_snapshot={
                "org_id": None,
                "subscription": None,
                "org_roles": [],
                "features": {},
                "modules": {},
                "limits": {},
                "capabilities": [],
                "computed": {"hash": "", "computed_at": datetime.now(timezone.utc).isoformat()},
            },
            capabilities=[],
            nav_sections=None,
            partner=None,
            access_state=PortalAccessState.TECH_ERROR,
            access_reason="portal_me_failed",
            billing=None,
        )
