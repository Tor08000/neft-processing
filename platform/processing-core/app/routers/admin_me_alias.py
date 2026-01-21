from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.portal_me import PortalMeResponse
from app.security.rbac.principal import Principal, get_principal
from app.services.portal_me import build_portal_me

router = APIRouter(prefix="/v1/admin", tags=["admin-me"])


@router.get("/me", response_model=PortalMeResponse)
def get_admin_me(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> PortalMeResponse:
    return build_portal_me(db, token=principal.raw_claims)


__all__ = ["router"]
