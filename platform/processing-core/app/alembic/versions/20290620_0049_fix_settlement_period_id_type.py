"""Fix settlement_period_id type.

Revision ID: 20290620_0049_fix_settlement_period_id_type
Revises: 20290615_0048_merge_heads
Create Date: 2029-06-20 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20290620_0049_fix_settlement_period_id_type"
down_revision = "20290615_0048_merge_heads"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    op.alter_column(
        "invoice_settlement_allocations",
        "settlement_period_id",
        existing_type=sa.String(length=36),
        type_=postgresql.UUID(as_uuid=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.alter_column(
        "invoice_settlement_allocations",
        "settlement_period_id",
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(length=36),
        schema=SCHEMA,
    )
