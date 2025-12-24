"""Add invoice refunds tracking fields.

Revision ID: 0046_invoice_refunds
Revises: 0039_billing_finance_idempotency
Create Date: 2028-01-12 00:46:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import (
    SCHEMA,
    column_exists,
    constraint_exists,
    ensure_pg_enum_value,
    index_exists,
    is_postgres,
)

# revision identifiers, used by Alembic.
revision = "0046_invoice_refunds"
down_revision = "0039_billing_finance_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    ensure_pg_enum_value(bind, "credit_note_status", "REVERSED", schema=SCHEMA)

    if not column_exists(bind, "credit_notes", "provider", schema=SCHEMA):
        op.add_column(
            "credit_notes",
            sa.Column("provider", sa.String(length=64), nullable=True),
            schema=SCHEMA,
        )

    if not column_exists(bind, "credit_notes", "external_ref", schema=SCHEMA):
        op.add_column(
            "credit_notes",
            sa.Column("external_ref", sa.String(length=128), nullable=True),
            schema=SCHEMA,
        )

    if not index_exists(bind, "uq_credit_notes_provider_external_ref", schema=SCHEMA):
        op.create_index(
            "uq_credit_notes_provider_external_ref",
            "credit_notes",
            ["provider", "external_ref"],
            unique=True,
            schema=SCHEMA,
            postgresql_where=sa.text("external_ref IS NOT NULL"),
        )

    if not constraint_exists(bind, "credit_notes", "ck_credit_notes_amount_positive", schema=SCHEMA):
        op.create_check_constraint(
            "ck_credit_notes_amount_positive",
            "credit_notes",
            "amount > 0",
            schema=SCHEMA,
        )

    if not column_exists(bind, "invoices", "amount_refunded", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("amount_refunded", sa.BigInteger(), nullable=False, server_default="0"),
            schema=SCHEMA,
        )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
