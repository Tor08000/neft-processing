"""operations product fields

Revision ID: 20251206_0004_operations_product_fields
Revises: 20251124_0003_merchants_terminals_cards
Create Date: 2025-12-06 00:04:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import (
    column_exists,
    create_index_if_not_exists,
    drop_index_if_exists,
    table_exists,
)


# revision identifiers, used by Alembic.
revision = "20251206_0004_operations_product_fields"
down_revision = "20251124_0003_merchants_terminals_cards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "operations"):
        if not column_exists(bind, "operations", "mcc"):
            op.add_column("operations", sa.Column("mcc", sa.String(length=32), nullable=True))
        if not column_exists(bind, "operations", "product_code"):
            op.add_column(
                "operations",
                sa.Column("product_code", sa.String(length=64), nullable=True),
            )
        if not column_exists(bind, "operations", "product_category"):
            op.add_column(
                "operations",
                sa.Column("product_category", sa.String(length=64), nullable=True),
            )

        create_index_if_not_exists(bind, "ix_operations_mcc", "operations", ["mcc"], unique=False)
        create_index_if_not_exists(
            bind,
            "ix_operations_product_category",
            "operations",
            ["product_category"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    drop_index_if_exists(bind, "ix_operations_product_category", table_name="operations")
    drop_index_if_exists(bind, "ix_operations_mcc", table_name="operations")

    if table_exists(bind, "operations"):
        if column_exists(bind, "operations", "product_category"):
            op.drop_column("operations", "product_category")
        if column_exists(bind, "operations", "product_code"):
            op.drop_column("operations", "product_code")
        if column_exists(bind, "operations", "mcc"):
            op.drop_column("operations", "mcc")
