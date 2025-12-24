"""Add payout batches and items tables.

Revision ID: 20271230_0039_payout_batches
Revises: 20271220_0038_finance_invoice_extensions
Create Date: 2027-12-30 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20271230_0039_payout_batches"
down_revision = "20271220_0038_finance_invoice_extensions"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

PAYOUT_BATCH_STATE = ["DRAFT", "READY", "SENT", "SETTLED", "FAILED"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "payout_batch_state", PAYOUT_BATCH_STATE, schema=SCHEMA)
    payout_state_enum = safe_enum(bind, "payout_batch_state", PAYOUT_BATCH_STATE, schema=SCHEMA)

    payout_fk = "payout_batches.id" if not SCHEMA else f"{SCHEMA}.payout_batches.id"

    create_table_if_not_exists(
        bind,
        "payout_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", sa.String(length=64), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("state", payout_state_enum, nullable=False, server_default=PAYOUT_BATCH_STATE[0]),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_qty", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("operations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.CheckConstraint("date_from <= date_to", name="ck_payout_batches_period"),
        sa.UniqueConstraint(
            "tenant_id",
            "partner_id",
            "date_from",
            "date_to",
            name="uq_payout_batches_period",
        ),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "payout_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), sa.ForeignKey(payout_fk), nullable=False),
        sa.Column("azs_id", sa.String(length=64), nullable=True),
        sa.Column("product_id", sa.String(length=64), nullable=True),
        sa.Column("amount_gross", sa.Numeric(18, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("amount_net", sa.Numeric(18, 2), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("operations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("meta", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_payout_batches_partner_period",
        "payout_batches",
        ["partner_id", "date_from", "date_to"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_payout_batches_state",
        "payout_batches",
        ["state"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_payout_batches_tenant_partner",
        "payout_batches",
        ["tenant_id", "partner_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_payout_items_batch",
        "payout_items",
        ["batch_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "uq_payout_batches_provider_external_ref",
        "payout_batches",
        ["provider", "external_ref"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
