"""Marketplace settlement snapshots and partner payout policies.

Revision ID: 20299260_0154_mor_snapshot_payout_policy
Revises: 20299250_0153_marketplace_mor_settlement
Create Date: 2025-03-20 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

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


revision = "20299260_0154_mor_snapshot_payout_policy"
down_revision = "20299250_0153_marketplace_mor_settlement"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "marketplace_settlement_snapshots",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("settlement_id", GUID(), nullable=False),
        sa.Column("order_id", GUID(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("platform_fee", sa.Numeric(18, 4), nullable=False),
        sa.Column("penalties", sa.Numeric(18, 4), nullable=False),
        sa.Column("partner_net", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("settlement_id", name="uq_marketplace_settlement_snapshots_settlement"),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_marketplace_settlement_snapshots_settlement_id",
        "marketplace_settlement_snapshots",
        ["settlement_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_settlement_snapshots_order_id",
        "marketplace_settlement_snapshots",
        ["order_id"],
        schema=SCHEMA,
    )

    if not column_exists(bind, "marketplace_settlement_items", "settlement_snapshot_id", schema=SCHEMA):
        op.add_column(
            "marketplace_settlement_items",
            sa.Column("settlement_snapshot_id", GUID(), nullable=True),
            schema=SCHEMA,
        )

    ensure_pg_enum(bind, "partner_payout_schedule", ["WEEKLY", "BIWEEKLY", "MONTHLY"], schema=SCHEMA)
    payout_schedule_enum = safe_enum(
        bind, "partner_payout_schedule", ["WEEKLY", "BIWEEKLY", "MONTHLY"], schema=SCHEMA
    )

    create_table_if_not_exists(
        bind,
        "partner_payout_policies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("partner_org_id", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
        sa.Column("min_payout_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("payout_hold_days", sa.Numeric(10, 0), nullable=False, server_default="0"),
        sa.Column(
            "payout_schedule",
            payout_schedule_enum,
            nullable=False,
            server_default="WEEKLY",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_partner_payout_policies_org_currency",
        "partner_payout_policies",
        ["partner_org_id", "currency"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
