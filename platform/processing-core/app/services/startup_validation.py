from __future__ import annotations

import logging
import os
from collections.abc import Collection, Mapping, Sequence
from typing import Literal

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.db import DB_SCHEMA, get_engine

AuthHostMode = Literal["external", "embedded"]

BASE_REQUIRED_TABLES: tuple[str, ...] = (
    "alembic_version_core",
    "operations",
    "clients",
    "client_user_roles",
    "cards",
    "card_limits",
)
EMBEDDED_REQUIRED_TABLES: tuple[str, ...] = ("users",)


def get_auth_host_mode(environ: Mapping[str, str] | None = None) -> AuthHostMode:
    env = environ or os.environ
    raw_mode = (env.get("AUTH_HOST_MODE") or env.get("NEFT_AUTH_MODE") or "external").strip().lower()
    if raw_mode in {"external", "embedded"}:
        return raw_mode
    logging.getLogger(__name__).warning(
        "Unknown AUTH_HOST_MODE=%r, falling back to external", raw_mode
    )
    return "external"


def get_required_tables(auth_mode: AuthHostMode, schema: str = DB_SCHEMA) -> list[tuple[str, str]]:
    required = [(schema, table_name) for table_name in BASE_REQUIRED_TABLES]
    if auth_mode == "embedded":
        required.extend((schema, table_name) for table_name in EMBEDDED_REQUIRED_TABLES)
    return required


def get_missing_required_tables(existing_tables: Collection[str], auth_mode: AuthHostMode) -> list[str]:
    required_names = [table_name for _, table_name in get_required_tables(auth_mode)]
    existing = set(existing_tables)
    return [table_name for table_name in required_names if table_name not in existing]


def validate_required_tables(
    engine: Engine,
    *,
    schema: str = DB_SCHEMA,
    auth_mode: AuthHostMode,
) -> list[str]:
    inspector = inspect(engine)
    inspector_schema = None if inspector.dialect.name == "sqlite" else schema
    existing_tables: Sequence[str] = inspector.get_table_names(schema=inspector_schema)
    return get_missing_required_tables(existing_tables, auth_mode)


def _format_required_tables(auth_mode: AuthHostMode, schema: str = DB_SCHEMA) -> str:
    return ", ".join(
        f"{table_schema}.{table_name}"
        for table_schema, table_name in get_required_tables(auth_mode, schema)
    )


def main() -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    logger = logging.getLogger("startup_validation")

    auth_mode = get_auth_host_mode()
    logger.info("AUTH_HOST_MODE=%s", auth_mode)
    logger.info("Required tables for auth mode %s: %s", auth_mode, _format_required_tables(auth_mode))

    missing = validate_required_tables(get_engine(), auth_mode=auth_mode)
    if missing:
        suffix = " (users required only for embedded mode)" if "users" in missing else ""
        logger.error(
            "required tables missing after migrations (auth_mode=%s): %s%s",
            auth_mode,
            ", ".join(f"{DB_SCHEMA}.{table_name}" for table_name in missing),
            suffix,
        )
        return 1

    logger.info("required tables present for auth mode %s", auth_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
