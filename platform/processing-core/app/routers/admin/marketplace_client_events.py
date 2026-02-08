from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.marketplace.client_events import (
    ENTITY_TYPE_WHITELIST,
    EVENT_TYPE_WHITELIST,
    MarketplaceClientEventOut,
    MarketplaceClientEventsQueryResponse,
)
from app.services.marketplace_client_events_service import list_admin_client_events


router = APIRouter(prefix="/marketplace/client-events", tags=["admin"])


def _event_out(event) -> MarketplaceClientEventOut:
    return MarketplaceClientEventOut(
        id=str(event.id),
        ts=event.ts,
        client_ts=event.client_ts,
        client_id=str(event.client_id),
        tenant_id=event.tenant_id,
        user_id=str(event.user_id) if event.user_id else None,
        session_id=event.session_id,
        event_type=event.event_type.value if hasattr(event.event_type, "value") else event.event_type,
        entity_type=event.entity_type.value if hasattr(event.entity_type, "value") else event.entity_type,
        entity_id=str(event.entity_id) if event.entity_id else None,
        source=event.source.value if hasattr(event.source, "value") else event.source,
        page=event.page,
        utm=event.utm,
        payload=event.payload,
        request_id=event.request_id,
        idempotency_key=event.idempotency_key,
    )


@router.get("", response_model=MarketplaceClientEventsQueryResponse)
def list_client_events(
    client_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    event_type: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> MarketplaceClientEventsQueryResponse:
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id_required")
    if event_type and event_type not in EVENT_TYPE_WHITELIST:
        raise HTTPException(status_code=400, detail="invalid_event_type")
    if entity_type and entity_type not in ENTITY_TYPE_WHITELIST:
        raise HTTPException(status_code=400, detail="invalid_entity_type")
    items, total = list_admin_client_events(
        db,
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )
    return MarketplaceClientEventsQueryResponse(
        items=[_event_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
