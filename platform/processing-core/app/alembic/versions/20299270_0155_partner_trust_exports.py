"""Add partner trust export enums.

Revision ID: 20299270_0155_partner_trust_exports
Revises: 20299260_0154_mor_snapshot_payout_policy
Create Date: 2026-04-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from alembic_helpers import DB_SCHEMA, ensure_pg_enum_value, is_postgres


revision = "20299270_0155_partner_trust_exports"
down_revision = "20299260_0154_mor_snapshot_payout_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    ensure_pg_enum_value(bind, "export_job_report_type", "settlement_chain", schema=DB_SCHEMA)
    ensure_pg_enum_value(bind, "export_job_format", "ZIP", schema=DB_SCHEMA)


def downgrade() -> None:
    # Postgres enums do not support value removal safely.
    return
