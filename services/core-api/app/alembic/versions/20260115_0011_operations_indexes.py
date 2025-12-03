"""
add composite and partial indexes for operations journal

Revision ID: 20260115_0011_operations_indexes
Revises: 20260110_0010_clearing
Create Date: 2026-01-15 00:11:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260115_0011_operations_indexes"
down_revision = "20260110_0010_clearing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_operations_merchant_created_at_desc",
        "operations",
        ["merchant_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_operations_terminal_created_at_desc",
        "operations",
        ["terminal_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_operations_client_created_at_desc",
        "operations",
        ["client_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_operations_card_created_at_desc",
        "operations",
        ["card_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_operations_type_created_at_desc",
        "operations",
        ["operation_type", sa.text("created_at DESC")],
        unique=False,
    )

    op.create_index(
        "idx_operations_open_only",
        "operations",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'OPEN'"),
    )

    op.create_index(
        "idx_operations_created_brin",
        "operations",
        ["created_at"],
        unique=False,
        postgresql_using="brin",
    )


def downgrade() -> None:
    op.drop_index("idx_operations_created_brin", table_name="operations")
    op.drop_index("idx_operations_open_only", table_name="operations")
    op.drop_index("ix_operations_type_created_at_desc", table_name="operations")
    op.drop_index("ix_operations_card_created_at_desc", table_name="operations")
    op.drop_index("ix_operations_client_created_at_desc", table_name="operations")
    op.drop_index("ix_operations_terminal_created_at_desc", table_name="operations")
    op.drop_index("ix_operations_merchant_created_at_desc", table_name="operations")
