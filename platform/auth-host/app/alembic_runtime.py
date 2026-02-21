from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

import psycopg
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError

REQUIRED_AUTH_TABLES: tuple[str, ...] = (
    "tenants",
    "users",
    "sso_idp_configs",
)

AUTH_TABLE_RESET_ALLOWLIST: tuple[str, ...] = (
    "auth_sessions",
    "password_history",
    "refresh_tokens",
    "security_events",
    "sso_idp_configs",
    "sso_oidc_connections",
    "sso_oidc_identities",
    "sso_oidc_states",
    "tenants",
    "user_clients",
    "user_roles",
    "users",
)


@dataclass(slots=True)
class AlembicState:
    db_revision: str | None
    heads: tuple[str, ...]


@dataclass(slots=True)
class DbReadiness:
    available: bool
    missing_tables: tuple[str, ...]
    revision_matches_head: bool
    db_revision: str | None
    expected_head: str
    reason: str | None = None


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def make_alembic_config() -> Config:
    cfg = Config("/app/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    return cfg


def get_script_directory(cfg: Config) -> ScriptDirectory:
    return ScriptDirectory.from_config(cfg)


def fetch_db_revision(dsn: str) -> str | None:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.alembic_version')")
            if cur.fetchone()[0] is None:
                return None
            cur.execute("SELECT version_num FROM public.alembic_version")
            row = cur.fetchone()
            return row[0] if row else None


def fetch_missing_tables(dsn: str, *, required_tables: Iterable[str]) -> tuple[str, ...]:
    missing: list[str] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for table_name in required_tables:
                cur.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
                    (table_name,),
                )
                if cur.fetchone() is None:
                    missing.append(table_name)
    return tuple(missing)


def is_db_revision_known(script: ScriptDirectory, revision: str | None) -> bool:
    if not revision:
        return False
    try:
        return script.get_revision(revision) is not None
    except CommandError:
        return False


def should_reset_for_broken_revision(*, db_revision: str | None, revision_known: bool) -> bool:
    if db_revision is None:
        return False
    if revision_known:
        return False
    mode = (os.getenv("AUTH_DB_RECOVERY") or os.getenv("DEV_DB_RECOVERY") or "").strip().lower()
    if mode == "reset":
        return True
    return _bool_env("AUTH_ALEMBIC_AUTO_REPAIR", False)


def read_alembic_state(dsn: str) -> AlembicState:
    cfg = make_alembic_config()
    script = get_script_directory(cfg)
    return AlembicState(db_revision=fetch_db_revision(dsn), heads=tuple(script.get_heads()))


def check_db_readiness(dsn: str) -> DbReadiness:
    cfg = make_alembic_config()
    script = get_script_directory(cfg)
    heads = tuple(script.get_heads())
    expected_head = heads[0] if heads else ""

    try:
        db_revision = fetch_db_revision(dsn)
        missing_tables = fetch_missing_tables(dsn, required_tables=REQUIRED_AUTH_TABLES)
    except Exception as exc:
        return DbReadiness(
            available=False,
            missing_tables=(),
            revision_matches_head=False,
            db_revision=None,
            expected_head=expected_head,
            reason=f"db_unavailable:{exc}",
        )

    revision_matches_head = bool(expected_head) and db_revision == expected_head
    if missing_tables:
        return DbReadiness(
            available=True,
            missing_tables=missing_tables,
            revision_matches_head=revision_matches_head,
            db_revision=db_revision,
            expected_head=expected_head,
            reason="missing_required_tables",
        )

    if not db_revision:
        return DbReadiness(
            available=True,
            missing_tables=(),
            revision_matches_head=False,
            db_revision=db_revision,
            expected_head=expected_head,
            reason="missing_alembic_version",
        )

    if not is_db_revision_known(script, db_revision):
        return DbReadiness(
            available=True,
            missing_tables=(),
            revision_matches_head=False,
            db_revision=db_revision,
            expected_head=expected_head,
            reason="unknown_db_revision",
        )

    if not revision_matches_head:
        return DbReadiness(
            available=True,
            missing_tables=(),
            revision_matches_head=False,
            db_revision=db_revision,
            expected_head=expected_head,
            reason="db_revision_not_at_head",
        )

    return DbReadiness(
        available=True,
        missing_tables=(),
        revision_matches_head=True,
        db_revision=db_revision,
        expected_head=expected_head,
        reason=None,
    )
