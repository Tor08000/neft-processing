"""Make legacy marketplace order fields nullable.

Revision ID: 20299380_0166_marketplace_orders_nullable_legacy_fields
Revises: 20299370_0165_marketplace_orders_lifecycle_v1
Create Date: 2025-02-20 00:00:01.000000
"""

from __future__ import annotations

from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists


revision = "20299380_0166_marketplace_orders_nullable_legacy_fields"
down_revision = "20299370_0165_marketplace_orders_lifecycle_v1"
branch_labels = None
depends_on = None


def _make_nullable(table: str, column: str) -> None:
    bind = op.get_bind()
    if not column_exists(bind, table, column, schema=DB_SCHEMA):
        return
    op.alter_column(table, column, schema=DB_SCHEMA, nullable=True)


def upgrade() -> None:
    _make_nullable("marketplace_orders", "product_id")
    _make_nullable("marketplace_orders", "quantity")
    _make_nullable("marketplace_orders", "price")
    _make_nullable("marketplace_orders", "discount")
    _make_nullable("marketplace_orders", "final_price")


def downgrade() -> None:
    pass
