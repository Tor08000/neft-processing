from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.card import Card
from app.models.client import Client
from app.schemas.admin_dashboard import (
    CardListResponse,
    CardShort,
    ClientListResponse,
    ClientShort,
)
from app.services.admin_auth import require_admin

router = APIRouter(
    prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


@router.get("/clients", response_model=ClientListResponse)
def list_clients(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    client_id: str | None = None,
    name: str | None = None,
    status: str | None = None,
    external_id: str | None = None,
    db: Session = Depends(get_db),
) -> ClientListResponse:
    query = db.query(Client)

    if client_id:
        try:
            parsed_client_id = UUID(client_id)
        except ValueError:
            return ClientListResponse(items=[], total=0, limit=limit, offset=offset)

        query = query.filter(Client.id == parsed_client_id)
    if name:
        query = query.filter(Client.name.ilike(f"%{name}%"))
    if status and hasattr(Client, "status"):
        query = query.filter(getattr(Client, "status") == status)
    if external_id:
        query = query.filter(Client.external_id == external_id)

    total = query.count()
    items: List[Client] = (
        query.order_by(Client.created_at.desc(), Client.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    serialized = [
        ClientShort(
            client_id=str(item.id),
            name=getattr(item, "name", None),
            status=getattr(item, "status", None),
            created_at=item.created_at,
        )
        for item in items
    ]

    return ClientListResponse(items=serialized, total=total, limit=limit, offset=offset)


@router.get("/cards", response_model=CardListResponse)
def list_cards(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    card_id: str | None = None,
    client_id: str | None = None,
    status: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
) -> CardListResponse:
    query = db.query(Card)

    if card_id:
        query = query.filter(Card.id == card_id)
    if client_id:
        query = query.filter(Card.client_id == client_id)
    if status:
        query = query.filter(Card.status == status)
    if active is not None and hasattr(Card, "active"):
        query = query.filter(getattr(Card, "active") == active)

    total = query.count()
    items: List[Card] = (
        query.order_by(Card.created_at.desc(), Card.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    serialized = [
        CardShort(
            card_id=item.id,
            client_id=item.client_id,
            status=getattr(item, "status", None),
            active=getattr(item, "active", None),
            created_at=item.created_at,
        )
        for item in items
    ]

    return CardListResponse(items=serialized, total=total, limit=limit, offset=offset)
