from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.logistics import LogisticsETASnapshotOut
from app.services.audit_service import request_context_from_request
from app.services.logistics import eta

router = APIRouter(prefix="/logistics", tags=["admin", "logistics"])


@router.post("/orders/{order_id}/eta/recompute", response_model=LogisticsETASnapshotOut)
def recompute_eta_endpoint(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> LogisticsETASnapshotOut:
    snapshot = eta.compute_eta_snapshot(
        db,
        order_id=order_id,
        reason="admin_recompute",
        request_ctx=request_context_from_request(request),
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="eta_not_available")
    return LogisticsETASnapshotOut.model_validate(snapshot)
