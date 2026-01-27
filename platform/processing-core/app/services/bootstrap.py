from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.card import Card
from app.models.merchant import Merchant
from app.models.terminal import Terminal
from app.db import DB_SCHEMA, get_sessionmaker
from app.services.legal_gate import ensure_default_legal_documents

DEFAULT_MERCHANT_ID = "M-001"
DEFAULT_TERMINAL_ID = "T-001"
DEFAULT_CARD_ID = "CARD-001"
DEFAULT_CLIENT_ID = "CLIENT-123"
DEFAULT_DEMO_CLIENT_UUID = "00000000-0000-0000-0000-000000000001"
DEV_ENVS = {"local", "dev", "development", "test"}


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

        ensure_default_legal_documents(db)

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


def _is_dev_env() -> bool:
    return os.getenv("NEFT_ENV", "local").lower() in DEV_ENVS


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _filter_columns(table_name: str, db: Session, values: dict[str, object]) -> dict[str, object]:
    engine = db.get_bind()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = :table
                """
            ),
            {"schema": DB_SCHEMA, "table": table_name},
        ).fetchall()
    columns = {row[0] for row in rows}
    return {key: value for key, value in values.items() if key in columns}


def ensure_demo_client(db: Session | None = None) -> None:
    logger = logging.getLogger(__name__)
    if not _is_dev_env():
        return

    session_provided = db is not None
    session_factory = get_sessionmaker()
    db = db or session_factory()

    try:
        client_id = os.getenv("NEFT_DEMO_CLIENT_UUID", DEFAULT_DEMO_CLIENT_UUID)
        if not _is_uuid(client_id):
            logger.warning("Invalid NEFT_DEMO_CLIENT_UUID=%s; skipping demo seed", client_id)
            return

        conn = db.connection()
        tables = conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema
                """
            ),
            {"schema": DB_SCHEMA},
        ).fetchall()
        table_names = {row[0] for row in tables}

        if "clients" in table_names:
            clients = conn.execute(
                text(
                    f"""
                    SELECT id, name, status
                    FROM {DB_SCHEMA}.clients
                    WHERE id = :client_id
                    """
                ),
                {"client_id": client_id},
            ).mappings().first()
            name = os.getenv("NEFT_DEMO_CLIENT_NAME") or os.getenv("NEFT_DEMO_ORG_NAME") or "Demo Client"
            values = {
                "id": client_id,
                "name": clients.get("name") if clients and clients.get("name") else name,
                "external_id": os.getenv("NEFT_DEMO_ORG_NAME", "demo-client"),
                "full_name": clients.get("name") if clients and clients.get("name") else name,
                "status": clients.get("status") if clients and clients.get("status") else "ACTIVE",
            }
            values = _filter_columns("clients", db, values)
            if clients:
                assignments = ", ".join(f"{key} = :{key}" for key in values if key != "id")
                if assignments:
                    conn.execute(
                        text(f"UPDATE {DB_SCHEMA}.clients SET {assignments} WHERE id = :id"),
                        values,
                    )
            else:
                columns = ", ".join(values.keys())
                placeholders = ", ".join(f":{key}" for key in values)
                conn.execute(
                    text(f"INSERT INTO {DB_SCHEMA}.clients ({columns}) VALUES ({placeholders})"),
                    values,
                )

        if "orgs" in table_names:
            org_id_raw = os.getenv("NEFT_DEMO_ORG_ID", "1")
            try:
                org_id = int(org_id_raw)
            except (TypeError, ValueError):
                org_id = None
            if org_id is not None:
                org_values = {
                    "id": org_id,
                    "name": os.getenv("NEFT_DEMO_ORG_NAME", "demo-client"),
                    "status": "ACTIVE",
                    "roles": json.dumps(["CLIENT"]),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                org_values = _filter_columns("orgs", db, org_values)
                existing_org = conn.execute(
                    text(
                        f"""
                        SELECT id
                        FROM {DB_SCHEMA}.orgs
                        WHERE id = :org_id
                        """
                    ),
                    {"org_id": org_id},
                ).mappings().first()
                if existing_org:
                    assignments = ", ".join(f"{key} = :{key}" for key in org_values)
                    org_values["id"] = org_id
                    conn.execute(
                        text(f"UPDATE {DB_SCHEMA}.orgs SET {assignments} WHERE id = :id"),
                        org_values,
                    )
                else:
                    columns = ", ".join(org_values.keys())
                    placeholders = ", ".join(f":{key}" for key in org_values)
                    conn.execute(
                        text(f"INSERT INTO {DB_SCHEMA}.orgs ({columns}) VALUES ({placeholders})"),
                        org_values,
                    )

        db.commit()
    except SQLAlchemyError as exc:  # pragma: no cover - safeguard on startup
        db.rollback()
        logger.warning("Skipping demo bootstrap: database unavailable or schema missing (%s)", exc)
    finally:
        if not session_provided:
            db.close()
