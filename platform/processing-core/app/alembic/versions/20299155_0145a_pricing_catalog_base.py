"""Pricing catalog base table.

Revision ID: 20299155_0145a_pricing_catalog_base
Revises: 20299150_0145_service_slo_framework
Create Date: 2026-02-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA


revision = "20299155_0145a_pricing_catalog_base"
down_revision = "20299150_0145_service_slo_framework"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pricing_catalog",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=True, server_default="RUB"),
        sa.Column("price_monthly", sa.Numeric(18, 2), nullable=True),
        sa.Column("price_yearly", sa.Numeric(18, 2), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("item_type IN ('PLAN', 'ADDON')", name="pricing_catalog_item_type_check"),
        sa.CheckConstraint("currency IN ('RUB', 'USD', 'EUR')"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to > effective_from"),
        schema=DB_SCHEMA,
    )
    op.create_index(
        "idx_pricing_catalog_effective",
        "pricing_catalog",
        ["effective_from", "effective_to"],
        schema=DB_SCHEMA,
    )
    op.create_index(
        "idx_pricing_catalog_item",
        "pricing_catalog",
        ["item_type", "item_id", "effective_from"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("idx_pricing_catalog_item", table_name="pricing_catalog", schema=DB_SCHEMA)
    op.drop_index("idx_pricing_catalog_effective", table_name="pricing_catalog", schema=DB_SCHEMA)
    op.drop_table("pricing_catalog", schema=DB_SCHEMA)
