from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

import requests
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
AUTH_INTERNAL_LOOKUP_URL = os.getenv(
    "AUTH_INTERNAL_LOOKUP_URL",
    "http://auth-host:8000/api/auth/internal/users/lookup",
)


def _lookup_auth_user_id(email: str, logger: logging.Logger) -> str | None:
    try:
        response = requests.get(
            AUTH_INTERNAL_LOOKUP_URL,
            params={"email": email.strip().lower()},
            timeout=3,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        user_id = payload.get("user_id")
        return str(user_id) if user_id else None
    except requests.RequestException as exc:
        logger.warning("Auth-host lookup unavailable for %s: %s", email, exc)
        return None


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


def _is_empty_value(value: object | None) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


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
                    SELECT *
                    FROM {DB_SCHEMA}.clients
                    WHERE id = :client_id
                    """
                ),
                {"client_id": client_id},
            ).mappings().first()
            name = os.getenv("NEFT_DEMO_CLIENT_NAME") or os.getenv("NEFT_DEMO_ORG_NAME") or "Demo Client"
            if clients:
                update_values = {"id": client_id}
                if _is_empty_value(clients.get("name")):
                    update_values["name"] = name
                if _is_empty_value(clients.get("full_name")):
                    update_values["full_name"] = name
                if _is_empty_value(clients.get("status")):
                    update_values["status"] = "ACTIVE"
                if _is_empty_value(clients.get("external_id")):
                    update_values["external_id"] = os.getenv("NEFT_DEMO_ORG_NAME", "demo-client")
                update_values = _filter_columns("clients", db, update_values)
                assignments = ", ".join(f"{key} = :{key}" for key in update_values if key != "id")
                if assignments:
                    conn.execute(
                        text(f"UPDATE {DB_SCHEMA}.clients SET {assignments} WHERE id = :id"),
                        update_values,
                    )
            else:
                values = {
                    "id": client_id,
                    "name": name,
                    "external_id": os.getenv("NEFT_DEMO_ORG_NAME", "demo-client"),
                    "full_name": name,
                    "status": "ACTIVE",
                }
                values = _filter_columns("clients", db, values)
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


def ensure_demo_partner(db: Session | None = None) -> None:
    logger = logging.getLogger(__name__)
    if not _is_dev_env():
        return

    session_provided = db is not None
    session_factory = get_sessionmaker()
    db = db or session_factory()

    try:
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
        required = {"partners", "partner_user_roles", "partner_locations", "users"}
        if not required.issubset(table_names):
            return

        partner_row = conn.execute(
            text(f"SELECT id FROM {DB_SCHEMA}.partners WHERE code = 'demo-partner' LIMIT 1")
        ).mappings().first()
        if partner_row:
            partner_id = partner_row["id"]
        else:
            partner_id = conn.execute(
                text(
                    f"""
                    INSERT INTO {DB_SCHEMA}.partners (id, code, legal_name, partner_type, status, contacts)
                    VALUES (gen_random_uuid(), 'demo-partner', 'Demo Partner', 'OTHER', 'ACTIVE', '{{}}'::jsonb)
                    RETURNING id
                    """
                )
            ).scalar_one()

        user_row = conn.execute(
            text(f"SELECT id FROM {DB_SCHEMA}.users WHERE email = :email LIMIT 1"),
            {"email": "partner@neft.local"},
        ).mappings().first()
        if user_row:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {DB_SCHEMA}.partner_user_roles (id, partner_id, user_id, roles)
                    VALUES (gen_random_uuid(), :partner_id, :user_id, '["PARTNER_OWNER"]'::jsonb)
                    ON CONFLICT (partner_id, user_id)
                    DO UPDATE SET roles = excluded.roles
                    """
                ),
                {"partner_id": partner_id, "user_id": str(user_row["id"])},
            )

        conn.execute(
            text(
                f"""
                INSERT INTO {DB_SCHEMA}.partner_locations
                    (id, partner_id, external_id, code, title, address, city, region, status)
                SELECT gen_random_uuid(), :partner_id, 'demo-location-1', 'demo-1',
                       'Demo Location', 'Demo Address', 'Moscow', 'Moscow', 'ACTIVE'
                WHERE NOT EXISTS (
                    SELECT 1 FROM {DB_SCHEMA}.partner_locations
                    WHERE partner_id = :partner_id AND external_id = 'demo-location-1'
                )
                """
            ),
            {"partner_id": partner_id},
        )
        db.commit()
    except SQLAlchemyError as exc:  # pragma: no cover
        db.rollback()
        logger.warning("Skipping demo partner bootstrap: database unavailable or schema missing (%s)", exc)
    finally:
        if not session_provided:
            db.close()


def ensure_demo_portal_bindings(db: Session | None = None) -> None:
    logger = logging.getLogger(__name__)
    if not _is_dev_env():
        return

    session_provided = db is not None
    session_factory = get_sessionmaker()
    db = db or session_factory()

    try:
        conn = db.connection()
        table_names = {
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = :schema
                    """
                ),
                {"schema": DB_SCHEMA},
            ).fetchall()
        }

        required = {"clients", "accounts", "partner_accounts", "client_users", "client_user_roles", "partner_user_roles"}
        if not required.issubset(table_names):
            logger.warning("Skipping demo portal bindings: missing required tables in %s", DB_SCHEMA)
            return

        client_id = os.getenv("NEFT_DEMO_CLIENT_UUID", DEFAULT_DEMO_CLIENT_UUID)
        client_email = (os.getenv("NEFT_BOOTSTRAP_CLIENT_EMAIL") or "client@neft.local").strip().lower()
        partner_email = (os.getenv("NEFT_BOOTSTRAP_PARTNER_EMAIL") or "partner@neft.local").strip().lower()

        client_user_id = _lookup_auth_user_id(client_email, logger)
        partner_user_id = _lookup_auth_user_id(partner_email, logger)

        partner_id = conn.execute(
            text(f"SELECT id::text FROM {DB_SCHEMA}.partners WHERE code='demo-partner' LIMIT 1")
        ).scalar_one_or_none()

        conn.execute(
            text(
                f"""
                INSERT INTO {DB_SCHEMA}.accounts (client_id, owner_type, currency, type, status)
                SELECT :client_id, 'CLIENT', 'RUB', 'CLIENT_MAIN', 'ACTIVE'
                WHERE NOT EXISTS (
                    SELECT 1 FROM {DB_SCHEMA}.accounts
                    WHERE client_id=:client_id AND type='CLIENT_MAIN'
                )
                """
            ),
            {"client_id": client_id},
        )

        if partner_id:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {DB_SCHEMA}.partner_accounts (org_id, currency, balance_available, balance_pending, balance_blocked)
                    VALUES (:org_id, 'RUB', 0, 0, 0)
                    ON CONFLICT (org_id) DO NOTHING
                    """
                ),
                {"org_id": partner_id},
            )

        if client_user_id:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {DB_SCHEMA}.client_users (id, client_id, user_id, status)
                    VALUES (gen_random_uuid(), :client_id, :user_id, 'ACTIVE')
                    ON CONFLICT (client_id, user_id) DO UPDATE SET status='ACTIVE'
                    """
                ),
                {"client_id": client_id, "user_id": client_user_id},
            )
            conn.execute(
                text(
                    f"""
                    INSERT INTO {DB_SCHEMA}.client_user_roles (id, client_id, user_id, roles)
                    VALUES (gen_random_uuid(), :client_id, :user_id, '["CLIENT_OWNER"]'::jsonb)
                    ON CONFLICT (client_id, user_id) DO UPDATE SET roles='["CLIENT_OWNER"]'::jsonb
                    """
                ),
                {"client_id": client_id, "user_id": client_user_id},
            )

        if partner_id and partner_user_id:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {DB_SCHEMA}.partner_user_roles (id, partner_id, user_id, roles)
                    VALUES (gen_random_uuid(), :partner_id, :user_id, '["PARTNER_OWNER"]'::jsonb)
                    ON CONFLICT (partner_id, user_id) DO UPDATE SET roles='["PARTNER_OWNER"]'::jsonb
                    """
                ),
                {"partner_id": partner_id, "user_id": partner_user_id},
            )

        db.commit()
    except SQLAlchemyError as exc:  # pragma: no cover
        db.rollback()
        logger.warning("Skipping demo portal bindings bootstrap: %s", exc)
    finally:
        if not session_provided:
            db.close()
