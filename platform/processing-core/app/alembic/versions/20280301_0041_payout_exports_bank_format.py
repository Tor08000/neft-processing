"""Add bank format code to payout export files.

Revision ID: 20280301_0041_payout_exports_bank_format
Revises: 20280115_0040_payout_exports
Create Date: 2028-03-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import SCHEMA, column_exists, is_postgres

# revision identifiers, used by Alembic.
revision = "20280301_0041_payout_exports_bank_format"
down_revision = "20280115_0040_payout_exports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    if not column_exists(bind, "payout_export_files", "bank_format_code", schema=SCHEMA):
        op.add_column(
            "payout_export_files",
            sa.Column("bank_format_code", sa.String(length=64), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
