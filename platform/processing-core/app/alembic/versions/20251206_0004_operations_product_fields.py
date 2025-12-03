"""operations product fields

Revision ID: 20251206_0004_operations_product_fields
Revises: 20251124_0003_merchants_terminals_cards
Create Date: 2025-12-06 00:04:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251206_0004_operations_product_fields"
down_revision = "20251124_0003_merchants_terminals_cards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operations", sa.Column("mcc", sa.String(length=32), nullable=True))
    op.add_column(
        "operations",
        sa.Column("product_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "operations",
        sa.Column("product_category", sa.String(length=64), nullable=True),
    )

    op.create_index("ix_operations_mcc", "operations", ["mcc"], unique=False)
    op.create_index(
        "ix_operations_product_category", "operations", ["product_category"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_operations_product_category", table_name="operations")
    op.drop_index("ix_operations_mcc", table_name="operations")

    op.drop_column("operations", "product_category")
    op.drop_column("operations", "product_code")
    op.drop_column("operations", "mcc")
