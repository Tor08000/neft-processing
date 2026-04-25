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
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.models.terminal import Terminal
from app.db import DB_SCHEMA, get_sessionmaker
from app.services.legal_gate import ensure_default_legal_documents

DEFAULT_MERCHANT_ID = "M-001"
DEFAULT_TERMINAL_ID = "T-001"
DEFAULT_CARD_ID = "CARD-001"
DEFAULT_CLIENT_ID = "CLIENT-123"
DEFAULT_DEMO_CLIENT_UUID = "00000000-0000-0000-0000-000000000001"
DEFAULT_DEMO_PLAN_ID = "demo_control_individual_1m"
DEFAULT_DEMO_PLAN_CODE = "DEMO_CONTROL_INDIVIDUAL_1M"
DEFAULT_DEMO_PARTNER_CODE = "demo-partner"
DEFAULT_DEMO_PARTNER_EMAIL = "partner@neft.local"
DEV_ENVS = {"local", "dev", "development", "test"}
AUTH_INTERNAL_LOOKUP_URL = os.getenv(
    "AUTH_INTERNAL_LOOKUP_URL",
    "http://auth-host:8000/api/auth/internal/users/lookup",
)

DEFAULT_RISK_THRESHOLD_SETS = (
    ("global-payment-v1", RiskSubjectType.PAYMENT, RiskThresholdAction.PAYMENT),
    ("global-invoice-v1", RiskSubjectType.INVOICE, RiskThresholdAction.INVOICE),
    ("global-payout-v1", RiskSubjectType.PAYOUT, RiskThresholdAction.PAYOUT),
    ("global-document-finalize-v1", RiskSubjectType.DOCUMENT, RiskThresholdAction.DOCUMENT_FINALIZE),
    ("global-export-v1", RiskSubjectType.EXPORT, RiskThresholdAction.EXPORT),
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
        ensure_default_risk_threshold_sets(db)

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


def ensure_default_risk_threshold_sets(db: Session) -> None:
    """Create conservative global risk thresholds required by fail-closed decisions."""

    now = datetime.now(timezone.utc)
    for threshold_id, subject_type, action in DEFAULT_RISK_THRESHOLD_SETS:
        threshold = db.get(RiskThresholdSet, threshold_id)
        if threshold is None:
            db.add(
                RiskThresholdSet(
                    id=threshold_id,
                    subject_type=subject_type,
                    action=action,
                    scope=RiskThresholdScope.GLOBAL,
                    version=1,
                    active=True,
                    block_threshold=90,
                    review_threshold=70,
                    allow_threshold=0,
                    valid_from=now,
                    created_by="bootstrap",
                )
            )
            continue

        if threshold.created_by == "bootstrap":
            threshold.subject_type = subject_type
            threshold.action = action
            threshold.scope = RiskThresholdScope.GLOBAL
            threshold.version = threshold.version or 1
            threshold.active = True
            threshold.block_threshold = 90
            threshold.review_threshold = 70
            threshold.allow_threshold = 0
            threshold.valid_from = threshold.valid_from or now


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


def _normalize_org_roles(value: object | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            value = json.loads(stripped)
        except (TypeError, ValueError, json.JSONDecodeError):
            value = [stripped]
    if isinstance(value, (list, tuple, set)):
        return sorted({str(item).strip().upper() for item in value if str(item).strip()})
    return [str(value).strip().upper()]


def _merge_org_roles(existing: object | None, required: list[str] | tuple[str, ...] | set[str]) -> str:
    merged = set(_normalize_org_roles(existing))
    merged.update(str(role).strip().upper() for role in required if str(role).strip())
    return json.dumps(sorted(merged))


def _ensure_demo_subscription_seed(
    db: Session,
    *,
    conn,
    table_names: set[str],
    client_id: str,
    org_id: int,
) -> None:
    required = {"subscription_plans", "subscription_plan_modules", "client_subscriptions"}
    if not required.issubset(table_names):
        return

    plan_values = {
        "id": DEFAULT_DEMO_PLAN_ID,
        "code": DEFAULT_DEMO_PLAN_CODE,
        "version": 1,
        "billing_period_months": 1,
        "title": "Demo Control Individual 1M",
        "description": "Demo control plan for local seeded portal access",
        "currency": "RUB",
        "is_active": True,
        "price_cents": 0,
        "discount_percent": 0,
    }
    plan_values = _filter_columns("subscription_plans", db, plan_values)
    existing_plan = conn.execute(
        text(
            f"""
            SELECT id
            FROM {DB_SCHEMA}.subscription_plans
            WHERE code = :code OR id = :id
            LIMIT 1
            """
        ),
        {"code": DEFAULT_DEMO_PLAN_CODE, "id": DEFAULT_DEMO_PLAN_ID},
    ).mappings().first()
    plan_id = existing_plan["id"] if existing_plan else DEFAULT_DEMO_PLAN_ID
    if existing_plan:
        assignments = ", ".join(f"{key} = :{key}" for key in plan_values if key != "id")
        if assignments:
            plan_values["id"] = plan_id
            conn.execute(
                text(f"UPDATE {DB_SCHEMA}.subscription_plans SET {assignments} WHERE id = :id"),
                plan_values,
            )
    else:
        columns = ", ".join(plan_values.keys())
        placeholders = ", ".join(f":{key}" for key in plan_values)
        conn.execute(
            text(f"INSERT INTO {DB_SCHEMA}.subscription_plans ({columns}) VALUES ({placeholders})"),
            plan_values,
        )

    module_seed = {
        "FUEL_CORE": {"enabled": True, "tier": "control", "limits_json": json.dumps({"cards_max": 5})},
        "MARKETPLACE": {"enabled": True, "tier": "basic", "limits_json": json.dumps({"marketplace_discount_percent": 2})},
        "ANALYTICS": {"enabled": True, "tier": "standard", "limits_json": json.dumps({"exports_per_month": 10, "kpi_reports": True})},
        "SLA": {"enabled": True, "tier": "basic", "limits_json": json.dumps({"sla_first_response_minutes": 240, "sla_resolve_minutes": 2880})},
        "AI_ASSISTANT": {"enabled": True, "tier": "lite", "limits_json": json.dumps({"ai_tier": "lite"})},
        "EXPLAIN": {"enabled": True, "tier": "standard", "limits_json": json.dumps({"explain_depth": 2, "explain_diff": False, "what_if": "off"})},
        "PENALTIES": {"enabled": True, "tier": "monitoring", "limits_json": json.dumps({"penalties_mode": "monitoring"})},
        "BONUSES": {"enabled": True, "tier": "standard", "limits_json": json.dumps({"bonus_multiplier": 1.0})},
    }
    for module_code, payload in module_seed.items():
        module_values = {
            "plan_id": plan_id,
            "module_code": module_code,
            "enabled": payload["enabled"],
            "tier": payload["tier"],
            "limits_json": payload["limits_json"],
        }
        module_values = _filter_columns("subscription_plan_modules", db, module_values)
        existing_module = conn.execute(
            text(
                f"""
                SELECT module_code
                FROM {DB_SCHEMA}.subscription_plan_modules
                WHERE plan_id = :plan_id AND module_code = :module_code
                LIMIT 1
                """
            ),
            {"plan_id": plan_id, "module_code": module_code},
        ).mappings().first()
        if existing_module:
            assignments = ", ".join(f"{key} = :{key}" for key in module_values if key not in {"plan_id", "module_code"})
            if assignments:
                update_values = {
                    **module_values,
                    "plan_id": plan_id,
                    "module_code": module_code,
                }
                conn.execute(
                    text(
                        f"""
                        UPDATE {DB_SCHEMA}.subscription_plan_modules
                        SET {assignments}
                        WHERE plan_id = :plan_id AND module_code = :module_code
                        """
                    ),
                    update_values,
                )
            continue
        columns = ", ".join(module_values.keys())
        placeholders = ", ".join(f":{key}" for key in module_values)
        conn.execute(
            text(f"INSERT INTO {DB_SCHEMA}.subscription_plan_modules ({columns}) VALUES ({placeholders})"),
            module_values,
        )

    subscription_values = {
        "id": f"demo-sub-{org_id}",
        "tenant_id": org_id,
        "client_id": client_id,
        "plan_id": plan_id,
        "status": "ACTIVE",
        "created_at": datetime.now(timezone.utc),
        "start_at": datetime.now(timezone.utc),
    }
    subscription_values = _filter_columns("client_subscriptions", db, subscription_values)
    existing_subscription = conn.execute(
        text(
            f"""
            SELECT id
            FROM {DB_SCHEMA}.client_subscriptions
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC NULLS LAST
            LIMIT 1
            """
        ),
        {"tenant_id": org_id},
    ).mappings().first()
    if existing_subscription:
        assignments = ", ".join(f"{key} = :{key}" for key in subscription_values if key != "id")
        if assignments:
            subscription_values["id"] = existing_subscription["id"]
            conn.execute(
                text(f"UPDATE {DB_SCHEMA}.client_subscriptions SET {assignments} WHERE id = :id"),
                subscription_values,
            )
        return

    columns = ", ".join(subscription_values.keys())
    placeholders = ", ".join(f":{key}" for key in subscription_values)
    conn.execute(
        text(f"INSERT INTO {DB_SCHEMA}.client_subscriptions ({columns}) VALUES ({placeholders})"),
        subscription_values,
    )


def ensure_demo_partner_binding(
    db: Session,
    *,
    user_id: str | None,
    email: str | None,
    roles: list[str] | tuple[str, ...] | set[str] | None = None,
) -> bool:
    logger = logging.getLogger(__name__)
    if not _is_dev_env():
        return False

    expected_email = (
        os.getenv("NEFT_BOOTSTRAP_PARTNER_EMAIL")
        or os.getenv("NEFT_DEMO_PARTNER_EMAIL")
        or DEFAULT_DEMO_PARTNER_EMAIL
    ).strip().lower()
    normalized_email = str(email or "").strip().lower()
    if normalized_email != expected_email:
        return False

    normalized_roles = {str(role).upper() for role in (roles or []) if role}
    if normalized_roles and not any(role.startswith("PARTNER") for role in normalized_roles):
        return False

    resolved_user_id = str(user_id or "").strip() or _lookup_auth_user_id(expected_email, logger)
    if not resolved_user_id:
        return False

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
    required = {"partners", "partner_user_roles"}
    if not required.issubset(table_names):
        return False

    partner_id = conn.execute(
        text(f"SELECT id::text FROM {DB_SCHEMA}.partners WHERE code = :code LIMIT 1"),
        {"code": DEFAULT_DEMO_PARTNER_CODE},
    ).scalar_one_or_none()
    if not partner_id:
        partner_id = conn.execute(
            text(
                f"""
                INSERT INTO {DB_SCHEMA}.partners (id, name, type, allowed_ips, token, code, legal_name, partner_type, status, contacts)
                VALUES (gen_random_uuid(), 'Demo Partner', 'PARTNER', '[]'::jsonb, :token, :code, 'Demo Partner', 'OTHER', 'ACTIVE', '{{}}'::jsonb)
                RETURNING id::text
                """
            ),
            {"code": DEFAULT_DEMO_PARTNER_CODE, "token": "demo-partner-token"},
        ).scalar_one()

    conn.execute(
        text(
            f"""
            INSERT INTO {DB_SCHEMA}.partner_user_roles (id, partner_id, user_id, roles)
            VALUES (gen_random_uuid(), :partner_id, :user_id, '["PARTNER_OWNER"]'::jsonb)
            ON CONFLICT (partner_id, user_id)
            DO UPDATE SET roles = excluded.roles
            """
        ),
        {"partner_id": partner_id, "user_id": resolved_user_id},
    )
    db.commit()
    logger.info(
        "Repaired demo partner binding",
        extra={"partner_id": partner_id, "user_id": resolved_user_id, "email": normalized_email},
    )
    return True


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
            org_type = (os.getenv("NEFT_DEMO_CLIENT_ORG_TYPE") or "INDIVIDUAL").strip() or "INDIVIDUAL"
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
                if _is_empty_value(clients.get("org_type")):
                    update_values["org_type"] = org_type
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
                    "org_type": org_type,
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
                select_columns = "id, roles" if "roles" in org_values else "id"
                existing_org = conn.execute(
                    text(
                        f"""
                        SELECT {select_columns}
                        FROM {DB_SCHEMA}.orgs
                        WHERE id = :org_id
                        """
                    ),
                    {"org_id": org_id},
                ).mappings().first()
                if existing_org:
                    update_values = dict(org_values)
                    update_values["id"] = org_id
                    update_values.pop("created_at", None)
                    if "roles" in update_values:
                        update_values["roles"] = _merge_org_roles(existing_org.get("roles"), ("CLIENT",))
                    assignments = ", ".join(f"{key} = :{key}" for key in update_values if key != "id")
                    if assignments:
                        conn.execute(
                            text(f"UPDATE {DB_SCHEMA}.orgs SET {assignments} WHERE id = :id"),
                            update_values,
                        )
                else:
                    columns = ", ".join(org_values.keys())
                    placeholders = ", ".join(f":{key}" for key in org_values)
                    conn.execute(
                        text(f"INSERT INTO {DB_SCHEMA}.orgs ({columns}) VALUES ({placeholders})"),
                        org_values,
                    )
                _ensure_demo_subscription_seed(
                    db,
                    conn=conn,
                    table_names=table_names,
                    client_id=client_id,
                    org_id=org_id,
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
