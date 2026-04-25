from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.security.rbac.principal import Principal, get_principal
from app.db import get_db
from app.schemas.portal_me import PortalMeResponse
from app.services.portal_me import build_portal_me

# Canonical portal bootstrap/profile SSoT for client, partner, and admin surfaces.
router = APIRouter(prefix="/portal", tags=["portal-me"])
logger = logging.getLogger(__name__)


@router.get("/me", response_model=PortalMeResponse)
def get_portal_me(
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> PortalMeResponse:
    request_id = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
    return build_portal_me(db, token=principal.raw_claims, request_id=request_id)
