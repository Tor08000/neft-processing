"""Billing periods anchor for ledger-driven billing

Revision ID: 20271020_0033_billing_periods
Revises: 20271015_0032_operational_scenarios_v1
Create Date: 2027-10-20 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_pg_enum_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
)
from app.db.schema import resolve_db_schema
from app.db.types import GUID

# revision identifiers, used by Alembic.
revision = "20271020_0033_billing_periods"
down_revision = "20271015_0032_operational_scenarios_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

PERIOD_TYPES = ["DAILY", "MONTHLY"]
PERIOD_STATUSES = ["OPEN", "FINALIZED", "LOCKED"]


def _table_indexes() -> tuple[tuple[str, list[str]], ...]:
    return (
        ("ix_billing_periods_type_start", ["period_type", "start_at"]),
        ("ix_billing_periods_status", ["status"]),
        ("ix_billing_periods_start_at", ["start_at"]),
    )


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "billing_period_type", PERIOD_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "billing_period_status", PERIOD_STATUSES, schema=SCHEMA)

    period_type = safe_enum(bind, "billing_period_type", PERIOD_TYPES, schema=SCHEMA)
    period_status = safe_enum(bind, "billing_period_status", PERIOD_STATUSES, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "billing_periods",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("period_type", period_type, nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tz", sa.String(length=64), nullable=False),
        sa.Column("status", period_status, nullable=False, server_default=sa.text("'OPEN'")),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("period_type", "start_at", "end_at", name="uq_billing_period_scope"),
        schema=SCHEMA,
    )

    for index_name, columns in _table_indexes():
        create_index_if_not_exists(bind, index_name, "billing_periods", columns, schema=SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    drop_table_if_exists(bind, "billing_periods", schema=SCHEMA)
    drop_pg_enum_if_exists(bind, "billing_period_status", schema=SCHEMA)
    drop_pg_enum_if_exists(bind, "billing_period_type", schema=SCHEMA)
