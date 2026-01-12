"""Add external reference for invoice payments.

Revision ID: 0044_invoice_payments_external_ref
Revises: 20250210_0043_billing_invoice_clearing_batch_fields
Create Date: 2025-02-11 00:44:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import SCHEMA, column_exists, create_index_if_not_exists, is_postgres

# revision identifiers, used by Alembic.
revision = "0044_invoice_payments_external_ref"
down_revision = "20250210_0043_billing_invoice_clearing_batch_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    if not column_exists(bind, "invoice_payments", "external_ref", schema=SCHEMA):
        op.add_column(
            "invoice_payments",
            sa.Column("external_ref", sa.String(length=128), nullable=True),
            schema=SCHEMA,
        )

    create_index_if_not_exists(
        bind,
        "uq_invoice_payments_external_ref",
        "invoice_payments",
        ["external_ref"],
        schema=SCHEMA,
        unique=True,
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
