"""Add payout export files table.

Revision ID: 20280115_0040_payout_exports
Revises: 20271230_0039_payout_batches
Create Date: 2028-01-15 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20280115_0040_payout_exports"
down_revision = "20271230_0039_payout_batches"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

PAYOUT_EXPORT_FORMAT = ["CSV", "XLSX"]
PAYOUT_EXPORT_STATE = ["DRAFT", "GENERATED", "UPLOADED", "FAILED", "STALE"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "payout_export_format", PAYOUT_EXPORT_FORMAT, schema=SCHEMA)
    ensure_pg_enum(bind, "payout_export_state", PAYOUT_EXPORT_STATE, schema=SCHEMA)
    export_format_enum = safe_enum(bind, "payout_export_format", PAYOUT_EXPORT_FORMAT, schema=SCHEMA)
    export_state_enum = safe_enum(bind, "payout_export_state", PAYOUT_EXPORT_STATE, schema=SCHEMA)

    payout_fk = "payout_batches.id" if not SCHEMA else f"{SCHEMA}.payout_batches.id"

    create_table_if_not_exists(
        bind,
        "payout_export_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), sa.ForeignKey(payout_fk), nullable=False),
        sa.Column("format", export_format_enum, nullable=False),
        sa.Column("state", export_state_enum, nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("bucket", sa.String(length=128), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_payout_export_files_batch",
        "payout_export_files",
        ["batch_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_payout_export_files_state",
        "payout_export_files",
        ["state"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_payout_export_files_provider_ref",
        "payout_export_files",
        ["provider", "external_ref"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "uq_payout_export_files_provider_external_ref",
        "payout_export_files",
        ["provider", "external_ref"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    )
    create_index_if_not_exists(
        bind,
        "uq_payout_export_files_batch_format_provider_ref",
        "payout_export_files",
        ["batch_id", "format", "provider", "external_ref"],
        unique=True,
        schema=SCHEMA,
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
