from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.card import Card
from app.models.merchant import Merchant
from app.models.terminal import Terminal
from app.db import DB_SCHEMA, get_sessionmaker

DEFAULT_MERCHANT_ID = "M-001"
DEFAULT_TERMINAL_ID = "T-001"
DEFAULT_CARD_ID = "CARD-001"
DEFAULT_CLIENT_ID = "CLIENT-123"


def _log_guard_context(db: Session, logger: logging.Logger) -> None:
    connection = db.connection()
    server_addr, server_port, current_db = connection.execute(
        text("select inet_server_addr(), inet_server_port(), current_database()"),
    ).one()
    search_path = connection.execute(text("show search_path")).scalar_one_or_none()
    cards_locations = [
        f"{row.table_schema}.{row.table_name}"
        for row in connection.execute(
            text(
                """
                select table_schema, table_name
                from information_schema.tables
                where table_name = 'cards'
                order by 1,2
                """
            )
        )
    ]

    logger.info(
        "default refs guard target: server=%s:%s db=%s search_path=%s schema=%s",
        server_addr,
        server_port,
        current_db,
        search_path,
        DB_SCHEMA,
    )
    logger.info("default refs guard cards table entries: %s", cards_locations)


def ensure_default_refs(db: Session | None = None) -> None:
    logger = logging.getLogger(__name__)

    session_provided = db is not None
    session_factory = get_sessionmaker()
    db = db or session_factory()

    try:
        _log_guard_context(db, logger)

        column_exists = db.execute(
            text(
                """
                select 1
                from information_schema.columns
                where table_schema = :schema
                  and table_name = 'cards'
                  and column_name = 'created_at'
                """
            ),
            {"schema": DB_SCHEMA},
        ).scalar_one_or_none()

        if not column_exists:
            logger.fatal("cards.created_at column missing; aborting bootstrap")
            return

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
    finally:
        if not session_provided:
            db.close()
