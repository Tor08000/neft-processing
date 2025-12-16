from __future__ import annotations

"""Backwards-compatible shim for Alembic helpers."""

from app.alembic.helpers import (  # noqa: F401,F403
    MIN_VERSION_LENGTH,
    column_exists,
    constraint_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_mutable_predicate_or_expression_indexes,
    drop_table_if_exists,
    ensure_alembic_version_length,
    ensure_pg_enum,
    enum_exists,
    index_exists,
    is_postgres,
    is_sqlite,
    safe_enum,
    table_exists,
)

__all__ = [
    "MIN_VERSION_LENGTH",
    "column_exists",
    "constraint_exists",
    "create_index_if_not_exists",
    "create_table_if_not_exists",
    "drop_index_if_exists",
    "drop_mutable_predicate_or_expression_indexes",
    "drop_table_if_exists",
    "ensure_alembic_version_length",
    "ensure_pg_enum",
    "enum_exists",
    "index_exists",
    "is_postgres",
    "is_sqlite",
    "safe_enum",
    "table_exists",
]
