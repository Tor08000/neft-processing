"""merchants terminals cards

Revision ID: 20251124_0003
Revises: 20251118_0002_operations_journal
Create Date: 2025-11-24 00:03:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251124_0003"
down_revision = "20251118_0002_operations_journal"
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

    op.create_table(
        "cards",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("pan_masked", sa.String(length=32), nullable=True),
        sa.Column("expires_at", sa.String(length=16), nullable=True),
    )
    op.create_index("ix_cards_id", "cards", ["id"], unique=False)
    op.create_index("ix_cards_client_id", "cards", ["client_id"], unique=False)
    op.create_index("ix_cards_status", "cards", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cards_status", table_name="cards")
    op.drop_index("ix_cards_client_id", table_name="cards")
    op.drop_index("ix_cards_id", table_name="cards")
    op.drop_table("cards")

    op.drop_index("ix_terminals_status", table_name="terminals")
    op.drop_index("ix_terminals_merchant_id", table_name="terminals")
    op.drop_index("ix_terminals_id", table_name="terminals")
    op.drop_table("terminals")

    op.drop_index("ix_merchants_status", table_name="merchants")
    op.drop_index("ix_merchants_id", table_name="merchants")
    op.drop_table("merchants")
