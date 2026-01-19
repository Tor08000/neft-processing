"""Marketplace MoR settlement fields and platform revenue ledger.

Revision ID: 20299250_0153_marketplace_mor_settlement
Revises: 20299240_0152_partner_legal_profile
Create Date: 2025-03-15 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import (
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.schema import resolve_db_schema
from db.types import GUID


revision = "20299250_0153_marketplace_mor_settlement"
down_revision = "20299240_0152_partner_legal_profile"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "marketplace_payment_flow", ["PLATFORM_MOR"], schema=SCHEMA)
    payment_flow_enum = safe_enum(bind, "marketplace_payment_flow", ["PLATFORM_MOR"], schema=SCHEMA)

    if not column_exists(bind, "marketplace_orders", "payment_flow", schema=SCHEMA):
        op.add_column(
            "marketplace_orders",
            sa.Column(
                "payment_flow",
                payment_flow_enum,
                nullable=False,
                server_default="PLATFORM_MOR",
            ),
            schema=SCHEMA,
        )

    if not column_exists(bind, "marketplace_orders", "settlement_breakdown_json", schema=SCHEMA):
        op.add_column(
            "marketplace_orders",
            sa.Column("settlement_breakdown_json", JSON_TYPE, nullable=True),
            schema=SCHEMA,
        )

    create_table_if_not_exists(
        bind,
        "platform_revenue_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_id", GUID(), nullable=True, index=True),
        sa.Column("partner_id", GUID(), nullable=True, index=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("fee_basis", sa.String(length=16), nullable=False),
        sa.Column("meta_json", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_platform_revenue_entries_order_id",
        "platform_revenue_entries",
        ["order_id"],
        schema=SCHEMA,
    )
