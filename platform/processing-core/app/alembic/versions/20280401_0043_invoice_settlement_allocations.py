"""Add invoice settlement allocations.

Revision ID: 20280401_0043_invoice_settlement_allocations
Revises: 20280315_0042_client_actions_v1
Create Date: 2028-04-01 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20280401_0043_invoice_settlement_allocations"
down_revision = "20280315_0042_client_actions_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

SETTLEMENT_SOURCE_TYPE = ["PAYMENT", "CREDIT_NOTE", "REFUND"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "settlement_source_type", SETTLEMENT_SOURCE_TYPE, schema=SCHEMA)
    source_type_enum = safe_enum(bind, "settlement_source_type", SETTLEMENT_SOURCE_TYPE, schema=SCHEMA)

    invoice_fk = "invoices.id" if not SCHEMA else f"{SCHEMA}.invoices.id"
    period_fk = "billing_periods.id" if not SCHEMA else f"{SCHEMA}.billing_periods.id"

    create_table_if_not_exists(
        bind,
        "invoice_settlement_allocations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("invoice_id", sa.String(length=36), sa.ForeignKey(invoice_fk), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("settlement_period_id", sa.String(length=36), sa.ForeignKey(period_fk), nullable=False),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.UniqueConstraint("invoice_id", "source_type", "source_id", name="uq_settlement_alloc_scope"),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_alloc_invoice_id",
        "invoice_settlement_allocations",
        ["invoice_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_alloc_settlement_period_id",
        "invoice_settlement_allocations",
        ["settlement_period_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_alloc_client_period",
        "invoice_settlement_allocations",
        ["client_id", "settlement_period_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_alloc_source",
        "invoice_settlement_allocations",
        ["source_type", "source_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
