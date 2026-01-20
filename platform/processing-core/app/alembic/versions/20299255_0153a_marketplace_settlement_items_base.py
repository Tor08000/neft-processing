"""Create marketplace settlement items base table.

Revision ID: 20299255_0153a_marketplace_settlement_items_base
Revises: 20299250_0153_marketplace_mor_settlement
Create Date: 2026-03-18 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.schema import resolve_db_schema
from db.types import GUID


revision = "20299255_0153a_marketplace_settlement_items_base"
down_revision = "20299250_0153_marketplace_mor_settlement"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

SETTLEMENT_STATUS = ["OPEN", "INCLUDED_IN_PAYOUT", "SETTLED"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "marketplace_settlement_status", SETTLEMENT_STATUS, schema=SCHEMA)
    settlement_status_enum = safe_enum(
        bind, "marketplace_settlement_status", SETTLEMENT_STATUS, schema=SCHEMA
    )

    create_table_if_not_exists(
        bind,
        "marketplace_settlement_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("order_id", GUID(), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("commission_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("net_partner_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("penalty_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("adjustments_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("status", settlement_status_enum, nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_marketplace_settlement_items_order_id",
        "marketplace_settlement_items",
        ["order_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_settlement_items_period",
        "marketplace_settlement_items",
        ["period"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
