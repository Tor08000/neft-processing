"""Audit exports storage.

Revision ID: 20291800_0095_audit_exports_storage
Revises: 20291770_0094_case_events_hash_chain
Create Date: 2025-03-06 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    is_postgres,
    safe_enum,
)
from app.db.schema import resolve_db_schema


revision = "20291800_0095_audit_exports_storage"
down_revision = "20291770_0094_case_events_hash_chain"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

EXPORT_KINDS = ["EXPLAIN", "DIFF", "CASE"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "case_export_kind", EXPORT_KINDS, schema=SCHEMA)
    export_kind = safe_enum(bind, "case_export_kind", EXPORT_KINDS, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "case_exports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=True),
        sa.Column("kind", export_kind, nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False, unique=True),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_reason", sa.Text(), nullable=True),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_case_exports_case_created",
        "case_exports",
        ["case_id", "created_at"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_case_exports_kind_created",
        "case_exports",
        ["kind", "created_at"],
        schema=SCHEMA,
    )
    if is_postgres(bind):
        create_index_if_not_exists(
            bind,
            "ix_case_exports_active",
            "case_exports",
            ["deleted_at"],
            schema=SCHEMA,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )
    else:
        create_index_if_not_exists(
            bind,
            "ix_case_exports_active",
            "case_exports",
            ["deleted_at"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    pass
