"""create clearing table

Revision ID: 20260110_0009_create_clearing_table
Revises: 20260101_0008_billing_summary
Create Date: 2026-01-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20260110_0009_create_clearing_table"
down_revision = "20260101_0008_billing_summary"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _quote_schema(schema: str) -> str:
    if not schema:
        return ""
    escaped = schema.replace('"', '""')
    return f'"{escaped}"'


SCHEMA_QUOTED = _quote_schema(SCHEMA)


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "clearing_status", values=["PENDING"])
    clearing_status = safe_enum(bind, "clearing_status", values=["PENDING"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "clearing",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_date", sa.Date(), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            clearing_status,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "batch_date",
            "merchant_id",
            "currency",
            name="uq_clearing_date_merchant_currency",
        ),
    )
    create_index_if_not_exists(bind, "ix_clearing_batch_date", "clearing", ["batch_date"])
    create_index_if_not_exists(bind, "ix_clearing_merchant_id", "clearing", ["merchant_id"])
    create_index_if_not_exists(bind, "ix_clearing_currency", "clearing", ["currency"])
    create_index_if_not_exists(bind, "ix_clearing_status", "clearing", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    drop_index_if_exists(bind, "ix_clearing_status")
    drop_index_if_exists(bind, "ix_clearing_currency")
    drop_index_if_exists(bind, "ix_clearing_merchant_id")
    drop_index_if_exists(bind, "ix_clearing_batch_date")
    drop_table_if_exists(bind, "clearing")
    qualified_schema = f"{SCHEMA_QUOTED}." if SCHEMA_QUOTED else ""
    bind.exec_driver_sql(f"DROP TYPE IF EXISTS {qualified_schema}clearing_status")
