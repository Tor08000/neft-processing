from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.card import Card
from app.models.merchant import Merchant
from app.models.terminal import Terminal


def validate_terminal_auth_refs(
    db: Session, merchant_id: str, terminal_id: str, card_id: str, client_id: str
) -> None:
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant or merchant.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="merchant not found or inactive")

    terminal = (
        db.query(Terminal)
        .filter(Terminal.id == terminal_id, Terminal.merchant_id == merchant_id)
        .first()
    )
    if not terminal or terminal.status != "ACTIVE":
        raise HTTPException(
            status_code=400, detail="terminal not found or inactive for this merchant"
        )

    card = db.query(Card).filter(Card.id == card_id).first()
    if not card or card.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="card not found or inactive")

    if card.client_id != client_id:
        raise HTTPException(status_code=400, detail="card client mismatch")
