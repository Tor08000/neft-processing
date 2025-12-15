"""merchants terminals

Revision ID: 20251124_0003_merchants_terminals_cards
Revises: 20251120_0003_limits_rules_v2
Create Date: 2025-11-24 00:03:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251124_0003_merchants_terminals_cards"
down_revision = "20251121_0003a_extend_alembic_version_len"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchants",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_merchants_id", "merchants", ["id"], unique=False)
    op.create_index("ix_merchants_status", "merchants", ["status"], unique=False)

    op.create_table(
        "terminals",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("merchant_id", sa.String(length=64), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_terminals_id", "terminals", ["id"], unique=False)
    op.create_index("ix_terminals_merchant_id", "terminals", ["merchant_id"], unique=False)
    op.create_index("ix_terminals_status", "terminals", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_terminals_status", table_name="terminals")
    op.drop_index("ix_terminals_merchant_id", table_name="terminals")
    op.drop_index("ix_terminals_id", table_name="terminals")
    op.drop_table("terminals")

    op.drop_index("ix_merchants_status", table_name="merchants")
    op.drop_index("ix_merchants_id", table_name="merchants")
    op.drop_table("merchants")
