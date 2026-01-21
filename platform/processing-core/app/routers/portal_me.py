from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.services.portal_auth import require_portal_or_admin_user
from app.db import get_db
from app.schemas.portal_me import PortalMeResponse
from app.services.portal_me import build_portal_me

router = APIRouter(prefix="/portal", tags=["portal-me"])


@router.get("/me", response_model=PortalMeResponse)
def get_portal_me(
    token: dict = Depends(require_portal_or_admin_user),
    db: Session = Depends(get_db),
) -> PortalMeResponse:
    return build_portal_me(db, token=token)
