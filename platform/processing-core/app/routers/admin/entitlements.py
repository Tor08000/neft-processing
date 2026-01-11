from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.entitlements import EntitlementsOut
from app.services.entitlements_service import get_entitlements

router = APIRouter(prefix="/entitlements", tags=["entitlements"])


@router.get("/resolve", response_model=EntitlementsOut)
def resolve_entitlements(
    client_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> EntitlementsOut:
    entitlements = get_entitlements(db, client_id=client_id)
    payload = {
        "client_id": client_id,
        "plan_code": entitlements.plan_code,
        "price_version_id": entitlements.price_version_id,
        "modules": entitlements.modules,
        "limits": entitlements.limits,
        "pricing": entitlements.pricing,
    }
    return EntitlementsOut.model_validate(payload)


__all__ = ["router"]
