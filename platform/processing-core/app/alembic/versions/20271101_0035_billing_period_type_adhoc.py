"""Add ADHOC to billing_period_type enum

Revision ID: 20271101_0035_billing_period_type_adhoc
Revises: 20271030_0034_billing_hardening_v11
Create Date: 2027-11-01 00:00:00
"""
from __future__ import annotations

from alembic import op

from app.alembic.helpers import ensure_pg_enum_value, is_postgres
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20271101_0035_billing_period_type_adhoc"
down_revision = "20271030_0034_billing_hardening_v11"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema
BILLING_PERIOD_TYPE_VALUES = ["DAILY", "MONTHLY", "ADHOC"]


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    ensure_pg_enum_value(bind, "billing_period_type", "ADHOC", schema=SCHEMA)


def downgrade() -> None:
    # Removing a specific value from a PostgreSQL enum is not safe; leave as-is.
    pass
