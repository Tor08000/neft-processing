from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.marketplace_client_events import (
    MarketplaceClientEntityType,
    MarketplaceClientEvent,
    MarketplaceClientEventSource,
    MarketplaceClientEventType,
)
from app.schemas.marketplace.client_events import MarketplaceClientEventIn


def ingest_client_events(
    db: Session,
    *,
    tenant_id: int | None,
    client_id: str,
    user_id: str | None,
    request_id: str | None,
    events: list[MarketplaceClientEventIn],
) -> tuple[int, int]:
    idempotency_keys = {event.idempotency_key for event in events if event.idempotency_key}
    existing_keys: set[str] = set()
    if idempotency_keys:
        existing_keys = {
            row[0]
            for row in db.query(MarketplaceClientEvent.idempotency_key)
            .filter(
                MarketplaceClientEvent.client_id == client_id,
                MarketplaceClientEvent.idempotency_key.in_(idempotency_keys),
            )
            .all()
        }

    accepted = 0
    rejected = 0
    for event in events:
        if event.idempotency_key and event.idempotency_key in existing_keys:
            rejected += 1
            continue
        record = MarketplaceClientEvent(
            tenant_id=tenant_id,
            client_id=client_id,
            user_id=user_id,
            session_id=event.session_id,
            event_type=MarketplaceClientEventType(event.event_type),
            entity_type=MarketplaceClientEntityType(event.entity_type),
            entity_id=str(event.entity_id) if event.entity_id else None,
            source=MarketplaceClientEventSource(event.source),
            page=event.page,
            utm=event.utm,
            payload=event.payload,
            client_ts=event.client_ts,
            request_id=event.request_id or request_id,
            idempotency_key=event.idempotency_key,
        )
        db.add(record)
        accepted += 1
        if event.idempotency_key:
            existing_keys.add(event.idempotency_key)
    db.commit()
    return accepted, rejected


def list_client_events(
    db: Session,
    *,
    client_id: str,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MarketplaceClientEvent], int]:
    query = db.query(MarketplaceClientEvent).filter(MarketplaceClientEvent.client_id == client_id)
    if date_from:
        query = query.filter(MarketplaceClientEvent.ts >= date_from)
    if date_to:
        query = query.filter(MarketplaceClientEvent.ts <= date_to)
    if event_type:
        query = query.filter(MarketplaceClientEvent.event_type == MarketplaceClientEventType(event_type))
    if entity_type:
        query = query.filter(MarketplaceClientEvent.entity_type == MarketplaceClientEntityType(entity_type))
    if entity_id:
        query = query.filter(MarketplaceClientEvent.entity_id == entity_id)
    total = query.count()
    items = query.order_by(MarketplaceClientEvent.ts.desc()).offset(offset).limit(limit).all()
    return items, total


def list_admin_client_events(
    db: Session,
    *,
    client_id: str,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MarketplaceClientEvent], int]:
    return list_client_events(
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
