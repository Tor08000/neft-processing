"""Make ledger_entries.operation_id nullable

Revision ID: 20270620_0025_ledger_entries_operation_id_nullable
Revises: 20270601_0024_bootstrap_schema
Create Date: 2027-06-20 00:25:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20270620_0025_ledger_entries_operation_id_nullable"
down_revision = "20270601_0024_bootstrap_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "ledger_entries",
        "operation_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
        schema="public",
    )


def downgrade() -> None:
    op.alter_column(
        "ledger_entries",
        "operation_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
        schema="public",
    )
