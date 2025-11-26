from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.card import Card
from app.schemas.cards import CardCreate, CardSchema, CardUpdate, CardsPage

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("", response_model=CardsPage)
def list_cards(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> CardsPage:
    query = db.query(Card)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return CardsPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=CardSchema)
def create_card(payload: CardCreate = Body(...), db: Session = Depends(get_db)) -> CardSchema:
    card = Card(
        id=payload.id,
        client_id=payload.client_id,
        status=payload.status,
        pan_masked=payload.pan_masked,
        expires_at=payload.expires_at,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.get("/{card_id}", response_model=CardSchema)
def get_card(card_id: str, db: Session = Depends(get_db)) -> CardSchema:
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="card not found")
    return card


@router.patch("/{card_id}", response_model=CardSchema)
def update_card(
    card_id: str, payload: CardUpdate = Body(...), db: Session = Depends(get_db)
) -> CardSchema:
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="card not found")

    if payload.client_id is not None:
        card.client_id = payload.client_id
    if payload.status is not None:
        card.status = payload.status
    if payload.pan_masked is not None:
        card.pan_masked = payload.pan_masked
    if payload.expires_at is not None:
        card.expires_at = payload.expires_at

    db.commit()
    db.refresh(card)
    return card
