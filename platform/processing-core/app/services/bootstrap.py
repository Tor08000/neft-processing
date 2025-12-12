from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.card import Card
from app.models.merchant import Merchant
from app.models.terminal import Terminal

DEFAULT_MERCHANT_ID = "M-001"
DEFAULT_TERMINAL_ID = "T-001"
DEFAULT_CARD_ID = "CARD-001"
DEFAULT_CLIENT_ID = "CLIENT-123"


def ensure_default_refs(db: Session) -> None:
    logger = logging.getLogger(__name__)

    try:
        merchant = db.query(Merchant).filter(Merchant.id == DEFAULT_MERCHANT_ID).first()
        if not merchant:
            merchant = Merchant(
                id=DEFAULT_MERCHANT_ID,
                name="Default merchant",
                status="ACTIVE",
            )
            db.add(merchant)
        else:
            merchant.status = "ACTIVE"

        terminal = db.query(Terminal).filter(Terminal.id == DEFAULT_TERMINAL_ID).first()
        if not terminal:
            terminal = Terminal(
                id=DEFAULT_TERMINAL_ID,
                merchant_id=DEFAULT_MERCHANT_ID,
                status="ACTIVE",
                location="Default location",
            )
            db.add(terminal)
        else:
            terminal.merchant_id = DEFAULT_MERCHANT_ID
            terminal.status = "ACTIVE"

        card = db.query(Card).filter(Card.id == DEFAULT_CARD_ID).first()
        if not card:
            card = Card(
                id=DEFAULT_CARD_ID,
                client_id=DEFAULT_CLIENT_ID,
                status="ACTIVE",
                pan_masked="************0001",
            )
            db.add(card)
        else:
            card.client_id = DEFAULT_CLIENT_ID
            card.status = "ACTIVE"

        db.commit()
    except SQLAlchemyError as exc:  # pragma: no cover - safeguard on startup
        db.rollback()
        logger.warning(
            "Skipping default refs bootstrap: database unavailable or schema missing (%s)",
            exc,
        )
