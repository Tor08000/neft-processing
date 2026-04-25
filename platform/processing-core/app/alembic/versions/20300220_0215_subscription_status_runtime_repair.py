"""Ensure legacy subscription status enum supports runtime billing states.

Revision ID: 20300220_0215_subscription_status_runtime_repair
Revises: 20300210_0214_ledger_entries_operation_fk_repair
Create Date: 2030-01-19 01:45:00.000000
"""

from __future__ import annotations

from alembic import op

from alembic_helpers import DB_SCHEMA, ensure_pg_enum_value, is_postgres


revision = "20300220_0215_subscription_status_runtime_repair"
down_revision = "20300210_0214_ledger_entries_operation_fk_repair"
branch_labels = None
depends_on = None

SCHEMA = DB_SCHEMA
LEGACY_RUNTIME_STATUSES = (
    "FREE",
    "ACTIVE",
    "PAST_DUE",
    "SUSPENDED",
    "PENDING",
    "PAUSED",
    "GRACE",
    "EXPIRED",
    "CANCELLED",
)


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    for value in LEGACY_RUNTIME_STATUSES:
        ensure_pg_enum_value(bind, "subscription_status", value, schema=SCHEMA)


def downgrade() -> None:
    pass
