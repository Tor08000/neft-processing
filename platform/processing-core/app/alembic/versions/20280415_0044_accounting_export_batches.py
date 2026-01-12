"""Add accounting export batches table.

Revision ID: 20280415_0044_accounting_export_batches
Revises: 20280401_0043_invoice_settlement_allocations
Create Date: 2028-04-15 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.types import GUID
from db.schema import resolve_db_schema

revision = "20280415_0044_accounting_export_batches"
down_revision = "20280401_0043_invoice_settlement_allocations"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

ACCOUNTING_EXPORT_TYPE = ["CHARGES", "SETTLEMENT"]
ACCOUNTING_EXPORT_FORMAT = ["CSV", "JSON"]
ACCOUNTING_EXPORT_STATE = [
    "CREATED",
    "GENERATED",
    "UPLOADED",
    "DOWNLOADED",
    "CONFIRMED",
    "FAILED",
]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "accounting_export_type", ACCOUNTING_EXPORT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "accounting_export_format", ACCOUNTING_EXPORT_FORMAT, schema=SCHEMA)
    ensure_pg_enum(bind, "accounting_export_state", ACCOUNTING_EXPORT_STATE, schema=SCHEMA)
    export_type_enum = safe_enum(bind, "accounting_export_type", ACCOUNTING_EXPORT_TYPE, schema=SCHEMA)
    export_format_enum = safe_enum(bind, "accounting_export_format", ACCOUNTING_EXPORT_FORMAT, schema=SCHEMA)
    export_state_enum = safe_enum(bind, "accounting_export_state", ACCOUNTING_EXPORT_STATE, schema=SCHEMA)

    billing_period_fk = "billing_periods.id" if not SCHEMA else f"{SCHEMA}.billing_periods.id"

    create_table_if_not_exists(
        bind,
        "accounting_export_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("billing_period_id", GUID(), sa.ForeignKey(billing_period_fk), nullable=False),
        sa.Column("export_type", export_type_enum, nullable=False),
        sa.Column("format", export_format_enum, nullable=False),
        sa.Column("state", export_state_enum, nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("records_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("bucket", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "uq_accounting_export_batches_idempotency",
        "accounting_export_batches",
        ["idempotency_key"],
        unique=True,
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_accounting_export_batches_period",
        "accounting_export_batches",
        ["billing_period_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_accounting_export_batches_state",
        "accounting_export_batches",
        ["state"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_accounting_export_batches_type_format",
        "accounting_export_batches",
        ["export_type", "format"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
