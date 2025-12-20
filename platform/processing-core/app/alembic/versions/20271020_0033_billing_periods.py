"""Billing periods anchor for ledger-driven billing

Revision ID: 20271020_0033_billing_periods
Revises: 20271015_0032_operational_scenarios_v1
Create Date: 2027-10-20 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import create_table_if_not_exists, drop_table_if_exists, ensure_pg_enum, safe_enum
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20271020_0033_billing_periods"
down_revision = "20271015_0032_operational_scenarios_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

PERIOD_TYPES = ["DAILY", "MONTHLY"]
PERIOD_STATUSES = ["OPEN", "FINALIZED", "LOCKED"]


def _uuid_type(bind):
    return (
        sa.String(length=36)
        if getattr(getattr(bind, "dialect", None), "name", None) == "sqlite"
        else sa.dialects.postgresql.UUID(as_uuid=True)
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
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("period_type", period_type, nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tz", sa.String(length=64), nullable=False),
        sa.Column("status", period_status, nullable=False, server_default=PERIOD_STATUSES[0]),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("period_type", "start_at", "end_at", name="uq_billing_period_scope"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    drop_table_if_exists(bind, "billing_periods", schema=SCHEMA)
