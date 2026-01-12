"""Settlement v1 tables and enums.

Revision ID: 20291930_0101_settlement_v1
Revises: 20291920_0100_billing_flows_v1
Create Date: 2025-03-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import (
    SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    safe_enum,
)
from db.types import GUID


revision = "20291930_0101_settlement_v1"
down_revision = "20291920_0100_billing_flows_v1"
branch_labels = None
depends_on = None


SETTLEMENT_ACCOUNT_STATUS = ["ACTIVE", "SUSPENDED"]
SETTLEMENT_PERIOD_STATUS = ["OPEN", "CALCULATED", "APPROVED", "PAID"]
SETTLEMENT_ITEM_SOURCE_TYPE = ["invoice", "payment", "refund", "adjustment"]
SETTLEMENT_ITEM_DIRECTION = ["IN", "OUT"]
PAYOUT_STATUS = ["INITIATED", "SENT", "CONFIRMED", "FAILED"]


def _schema_prefix() -> str:
    if not SCHEMA:
        return ""
    return f"{SCHEMA}."


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "settlement_account_status", SETTLEMENT_ACCOUNT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "settlement_period_status", SETTLEMENT_PERIOD_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "settlement_item_source_type", SETTLEMENT_ITEM_SOURCE_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "settlement_item_direction", SETTLEMENT_ITEM_DIRECTION, schema=SCHEMA)
    ensure_pg_enum(bind, "payout_status", PAYOUT_STATUS, schema=SCHEMA)

    ensure_pg_enum_value(bind, "internal_ledger_account_type", "SETTLEMENT_CLEARING", schema=SCHEMA)
    ensure_pg_enum_value(bind, "internal_ledger_account_type", "PARTNER_SETTLEMENT", schema=SCHEMA)
    ensure_pg_enum_value(bind, "internal_ledger_transaction_type", "PARTNER_PAYOUT", schema=SCHEMA)

    ensure_pg_enum_value(bind, "case_event_type", "SETTLEMENT_CALCULATED", schema=SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "SETTLEMENT_APPROVED", schema=SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "PAYOUT_INITIATED", schema=SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "PAYOUT_CONFIRMED", schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "settlement_accounts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column(
            "status",
            safe_enum(bind, "settlement_account_status", SETTLEMENT_ACCOUNT_STATUS, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_settlement_accounts_partner_currency",
        "settlement_accounts",
        ["partner_id", "currency"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "settlement_periods",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            safe_enum(bind, "settlement_period_status", SETTLEMENT_PERIOD_STATUS, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("total_gross", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_fees", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_refunds", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_event_id", GUID(), nullable=True),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_settlement_periods_partner_status",
        "settlement_periods",
        ["partner_id", "status"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "settlement_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("settlement_period_id", GUID(), nullable=False),
        sa.Column(
            "source_type",
            safe_enum(bind, "settlement_item_source_type", SETTLEMENT_ITEM_SOURCE_TYPE, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("source_id", GUID(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "direction",
            safe_enum(bind, "settlement_item_direction", SETTLEMENT_ITEM_DIRECTION, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["settlement_period_id"],
            [f"{_schema_prefix()}settlement_periods.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_settlement_items_period",
        "settlement_items",
        ["settlement_period_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "payouts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("settlement_period_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", safe_enum(bind, "payout_status", PAYOUT_STATUS, schema=SCHEMA), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_payout_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("ledger_tx_id", GUID(), nullable=True),
        sa.Column("audit_event_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["settlement_period_id"],
            [f"{_schema_prefix()}settlement_periods.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_payouts_idempotency",
        "payouts",
        ["idempotency_key"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_payouts_partner_status",
        "payouts",
        ["partner_id", "status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
