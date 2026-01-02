from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.fleet_ingestion import FleetIngestJobOut, FleetIngestRequestIn
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services import fleet_ingestion_service

router = APIRouter(prefix="/api/internal/fleet", tags=["internal-fleet"])


def _request_ids(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("x-request-id"), request.headers.get("x-trace-id")


@router.post(
    "/transactions/ingest",
    response_model=FleetIngestJobOut,
    dependencies=[Depends(require_permission("admin:audit:*"))],
)
def ingest_transactions(
    payload: FleetIngestRequestIn,
    request: Request,
    principal: Principal = Depends(require_permission("admin:audit:*")),
    db: Session = Depends(get_db),
) -> FleetIngestJobOut:
    if not payload.items:
        raise HTTPException(status_code=400, detail="empty_batch")
    request_id, trace_id = _request_ids(request)
    job = fleet_ingestion_service.ingest_transactions(
        db,
        payload=payload,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return FleetIngestJobOut(
        id=str(job.id),
        provider_code=job.provider_code,
        batch_ref=job.batch_ref,
        idempotency_key=job.idempotency_key,
        status=job.status,
        received_at=job.received_at,
        total_count=job.total_count,
        inserted_count=job.inserted_count,
        deduped_count=job.deduped_count,
        error=job.error,
        audit_event_id=str(job.audit_event_id) if job.audit_event_id else None,
    )


__all__ = ["router"]
