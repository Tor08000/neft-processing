"""Add provider for invoice payments.

Revision ID: 0045_invoice_payments_provider
Revises: 0044_invoice_payments_external_ref
Create Date: 2025-02-12 00:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import SCHEMA, column_exists, is_postgres

# revision identifiers, used by Alembic.
revision = "0045_invoice_payments_provider"
down_revision = "0044_invoice_payments_external_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    if not column_exists(bind, "invoice_payments", "provider", schema=SCHEMA):
        op.add_column(
            "invoice_payments",
            sa.Column("provider", sa.String(length=64), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
