from __future__ import annotations

from typing import Sequence

from fastapi import Depends, HTTPException
from psycopg.errors import UndefinedTable
from sqlalchemy import inspect
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db import DB_SCHEMA, get_db

SCHEMA_NOT_INITIALIZED = HTTPException(status_code=503, detail="DB_SCHEMA_NOT_INITIALIZED")
REQUIRED_CORE_TABLES = ("operations", "accounts", "ledger_entries", "limit_configs")


def _is_missing_relation(exc: DBAPIError) -> bool:
    origin = getattr(exc, "orig", None) or exc
    if isinstance(origin, UndefinedTable):
        return True
    message = str(origin).lower()
    return "relation" in message and "does not exist" in message


def raise_schema_error_if_missing(exc: DBAPIError) -> None:
    if _is_missing_relation(exc):
        raise SCHEMA_NOT_INITIALIZED from exc


def ensure_tables_exist(db: Session, *, tables: Sequence[str]) -> None:
    try:
        inspector = inspect(db.bind)
        schema = None if inspector.dialect.name == "sqlite" else DB_SCHEMA
        existing = set(inspector.get_table_names(schema=schema))
    except DBAPIError as exc:  # pragma: no cover - defensive branch
        raise_schema_error_if_missing(exc)
        raise

    missing = set(tables) - existing
    if missing:
        raise SCHEMA_NOT_INITIALIZED


def require_operations_table(db: Session = Depends(get_db)) -> Session:
    """Dependency that ensures the operations table exists before handling the request."""

    ensure_tables_exist(db, tables=("operations",))
    return db
