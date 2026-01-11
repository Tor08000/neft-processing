from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.security.service_auth import require_service_scope
from app.services.abac import AbacResourceData, require_abac


router = APIRouter(prefix="/api/internal/security", tags=["internal-security"])


def _load_service_abac(db: Session = Depends(get_db)) -> AbacResourceData:
    return AbacResourceData(type="SYSTEM", attributes={"path": "/api/internal/security/ping"}, entitlements={})


@router.get("/ping")
def ping(
    principal=Depends(require_service_scope("rules:evaluate")),
    _abac=Depends(require_abac("rules:evaluate", _load_service_abac)),
) -> dict:
    return {"status": "ok", "service": principal.service_name}


__all__ = ["router"]
