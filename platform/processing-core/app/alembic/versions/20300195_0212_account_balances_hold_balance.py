"""Restore account balance hold column for dispute/refund posting flows.

Revision ID: 20300195_0212_account_balances_hold_balance
Revises: 20300190_0211_support_case_unification
Create Date: 2030-01-19 00:50:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, table_exists


revision = "20300195_0212_account_balances_hold_balance"
down_revision = "20300190_0211_support_case_unification"
branch_labels = None
depends_on = None

SCHEMA_PREFIX = f"{DB_SCHEMA}." if DB_SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "account_balances", schema=DB_SCHEMA):
        return

    if not column_exists(bind, "account_balances", "hold_balance", schema=DB_SCHEMA):
        op.add_column(
            "account_balances",
            sa.Column("hold_balance", sa.Numeric(18, 4), nullable=True, server_default="0"),
            schema=DB_SCHEMA,
        )

    op.execute(f"UPDATE {SCHEMA_PREFIX}account_balances SET hold_balance = 0 WHERE hold_balance IS NULL")
    op.alter_column(
        "account_balances",
        "hold_balance",
        existing_type=sa.Numeric(18, 4),
        nullable=False,
        server_default="0",
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    # Keep repair migration additive-only; historical rows may already depend on hold balances.
    pass
