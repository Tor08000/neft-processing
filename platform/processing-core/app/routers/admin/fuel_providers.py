from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.integrations.fuel.jobs import backfill_provider, list_ingest_jobs, list_raw_events, poll_provider, replay_raw_event
from app.integrations.fuel.models import FuelProviderConnection, FuelProviderRawEvent
from app.schemas.fuel_providers import (
    FuelProviderBackfillIn,
    FuelProviderBackfillOut,
    FuelProviderConnectionListResponse,
    FuelProviderConnectionOut,
    FuelProviderRawEventOut,
    FuelProviderSyncJobOut,
    FuelProviderSyncNowOut,
)
from app.services.admin_auth import require_admin
from app.services.audit_service import AuditService, request_context_from_request

router = APIRouter(prefix="/fleet/providers", tags=["admin", "fleet-providers"])


def _connection_to_schema(connection: FuelProviderConnection) -> FuelProviderConnectionOut:
    return FuelProviderConnectionOut(
        id=str(connection.id),
        client_id=connection.client_id,
        provider_code=connection.provider_code,
        status=connection.status,
        auth_type=connection.auth_type,
        config=connection.config,
        last_sync_at=connection.last_sync_at,
        created_at=connection.created_at,
    )


def _job_to_schema(job) -> FuelProviderSyncJobOut:
    return FuelProviderSyncJobOut(
        id=str(job.id),
        provider_code=job.provider_code,
        client_id=job.client_id,
        status=job.status,
        received_at=job.received_at,
        mode=job.mode.value if job.mode else None,
        window_start=job.window_start,
        window_end=job.window_end,
        total_count=job.total_count,
        inserted_count=job.inserted_count,
        deduped_count=job.deduped_count,
        error=job.error,
    )


def _raw_event_to_schema(event) -> FuelProviderRawEventOut:
    return FuelProviderRawEventOut(
        id=str(event.id),
        client_id=event.client_id,
        provider_code=event.provider_code,
        event_type=event.event_type,
        provider_event_id=event.provider_event_id,
        occurred_at=event.occurred_at,
        payload_redacted=event.payload_redacted,
        payload_hash=event.payload_hash,
        ingest_job_id=str(event.ingest_job_id) if event.ingest_job_id else None,
        created_at=event.created_at,
    )


@router.get("/connections", response_model=FuelProviderConnectionListResponse)
def list_connections(
    client_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> FuelProviderConnectionListResponse:
    query = db.query(FuelProviderConnection)
    if client_id:
        query = query.filter(FuelProviderConnection.client_id == client_id)
    connections = query.order_by(FuelProviderConnection.created_at.desc()).all()
    return FuelProviderConnectionListResponse(items=[_connection_to_schema(item) for item in connections])


@router.post("/{connection_id}/sync-now", response_model=FuelProviderSyncNowOut)
def admin_sync_now(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> FuelProviderSyncNowOut:
    connection = db.query(FuelProviderConnection).filter(FuelProviderConnection.id == connection_id).one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="provider_connection_not_found")
    now = datetime.now(timezone.utc)
    since = connection.last_sync_at or (now - timedelta(hours=1))
    job = poll_provider(
        db,
        connection=connection,
        since=since,
        until=now,
        request_id=request.headers.get("x-request-id"),
        trace_id=request.headers.get("x-trace-id"),
    )
    audit = AuditService(db).audit(
        event_type="FUEL_PROVIDER_SYNC_NOW",
        entity_type="fuel_provider_connection",
        entity_id=str(connection.id),
        action="sync",
        request_ctx=request_context_from_request(request, token=token),
        after={"job_id": str(job.id) if job else None},
    )
    if job:
        job.audit_event_id = audit.id
    db.commit()
    return FuelProviderSyncNowOut(job_id=str(job.id) if job else None, status="scheduled" if job else "no_data")


@router.post("/{connection_id}/backfill", response_model=FuelProviderBackfillOut)
def admin_backfill(
    connection_id: str,
    payload: FuelProviderBackfillIn,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> FuelProviderBackfillOut:
    connection = db.query(FuelProviderConnection).filter(FuelProviderConnection.id == connection_id).one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="provider_connection_not_found")
    jobs = backfill_provider(
        db,
        connection=connection,
        period_start=payload.period_start,
        period_end=payload.period_end,
        batch_hours=payload.batch_hours,
        request_id=request.headers.get("x-request-id"),
        trace_id=request.headers.get("x-trace-id"),
    )
    audit = AuditService(db).audit(
        event_type="FUEL_PROVIDER_BACKFILL",
        entity_type="fuel_provider_connection",
        entity_id=str(connection.id),
        action="backfill",
        request_ctx=request_context_from_request(request, token=token),
        after={"job_ids": [str(job.id) for job in jobs]},
    )
    for job in jobs:
        job.audit_event_id = audit.id
    db.commit()
    return FuelProviderBackfillOut(job_ids=[str(job.id) for job in jobs], status="scheduled")


@router.get("/jobs", response_model=list[FuelProviderSyncJobOut])
def list_jobs(
    provider_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> list[FuelProviderSyncJobOut]:
    jobs = list_ingest_jobs(db, provider_code=provider_code)
    return [_job_to_schema(item) for item in jobs]


@router.get("/raw", response_model=list[FuelProviderRawEventOut])
def list_raw(
    client_id: str | None = Query(default=None),
    provider_code: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> list[FuelProviderRawEventOut]:
    events = list_raw_events(db, client_id=client_id, provider_code=provider_code, start=start, end=end)
    return [_raw_event_to_schema(item) for item in events]


@router.post("/raw/{raw_event_id}/replay", response_model=FuelProviderSyncNowOut)
def replay_raw(
    raw_event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> FuelProviderSyncNowOut:
    raw_event = db.query(FuelProviderRawEvent).filter(FuelProviderRawEvent.id == raw_event_id).one_or_none()
    if not raw_event:
        raise HTTPException(status_code=404, detail="raw_event_not_found")
    job = replay_raw_event(
        db,
        raw_event=raw_event,
        request_id=request.headers.get("x-request-id"),
        trace_id=request.headers.get("x-trace-id"),
    )
    audit = AuditService(db).audit(
        event_type="FUEL_PROVIDER_REPLAY",
        entity_type="fuel_provider_raw_event",
        entity_id=str(raw_event.id),
        action="replay",
        request_ctx=request_context_from_request(request, token=token),
        after={"job_id": str(job.id) if job else None},
    )
    if job:
        job.audit_event_id = audit.id
    db.commit()
    return FuelProviderSyncNowOut(job_id=str(job.id) if job else None, status="scheduled" if job else "no_data")
