"""BI exports v1.1 upgrades.

Revision ID: 20291650_0087_bi_exports_v1_1
Revises: 20291640_0086_bi_mart_v1
Create Date: 2025-02-20 00:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.alembic.utils import (
    column_exists,
    create_table_if_not_exists,
    ensure_pg_enum_value,
    is_postgres,
    table_exists,
)

# revision identifiers, used by Alembic.
revision = "20291650_0087_bi_exports_v1_1"
down_revision = "20291640_0086_bi_mart_v1"
branch_labels = None
depends_on = None

BI_SCHEMA = "bi"


def _schema_name(bind) -> str | None:
    if is_postgres(bind):
        return BI_SCHEMA
    return None


def upgrade() -> None:
    bind = op.get_bind()
    schema = _schema_name(bind)

    if is_postgres(bind):
        ensure_pg_enum_value(bind, "bi_export_kind", "ORDER_EVENTS", schema=schema)
        ensure_pg_enum_value(bind, "bi_export_format", "JSONL", schema=schema)
        ensure_pg_enum_value(bind, "bi_export_format", "PARQUET", schema=schema)

    if table_exists(bind, "bi_export_batches", schema=schema):
        if not column_exists(bind, "bi_export_batches", "created_by", schema=schema):
            op.add_column("bi_export_batches", sa.Column("created_by", sa.String(128)), schema=schema)
        if not column_exists(bind, "bi_export_batches", "manifest_key", schema=schema):
            op.add_column("bi_export_batches", sa.Column("manifest_key", sa.String(512)), schema=schema)

    if not table_exists(bind, "bi_clickhouse_cursors", schema=schema):
        create_table_if_not_exists(
            bind,
            "bi_clickhouse_cursors",
            sa.Column("dataset", sa.String(64), primary_key=True),
            sa.Column("last_id", sa.String(128), nullable=True),
            sa.Column("last_occurred_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    schema = _schema_name(bind)

    op.drop_table("bi_clickhouse_cursors", schema=schema)
    if table_exists(bind, "bi_export_batches", schema=schema):
        if column_exists(bind, "bi_export_batches", "manifest_key", schema=schema):
            op.drop_column("bi_export_batches", "manifest_key", schema=schema)
        if column_exists(bind, "bi_export_batches", "created_by", schema=schema):
            op.drop_column("bi_export_batches", "created_by", schema=schema)
