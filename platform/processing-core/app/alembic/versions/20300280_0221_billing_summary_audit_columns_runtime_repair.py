"""Restore billing_summary audit columns expected by runtime projections.

Revision ID: 20300280_0221_billing_summary_audit_columns_runtime_repair
Revises: 20300270_0220_billing_summary_period_runtime_repair
Create Date: 2030-01-20 03:15:00.000000
"""

from __future__ import annotations

from alembic import op

from db.schema import resolve_db_schema


revision = "20300280_0221_billing_summary_audit_columns_runtime_repair"
down_revision = "20300270_0220_billing_summary_period_runtime_repair"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _table(name: str) -> str:
    return f"{_q(SCHEMA)}.{_q(name)}" if SCHEMA else _q(name)


def upgrade() -> None:
    bind = op.get_bind()

    bind.exec_driver_sql(
        f"ALTER TABLE {_table('billing_summary')} "
        "ADD COLUMN IF NOT EXISTS generated_at TIMESTAMPTZ NULL DEFAULT now()"
    )
    bind.exec_driver_sql(
        f"ALTER TABLE {_table('billing_summary')} "
        "ADD COLUMN IF NOT EXISTS hash VARCHAR(128) NULL"
    )
    bind.exec_driver_sql(
        f"CREATE INDEX IF NOT EXISTS ix_billing_summary_generated_at "
        f"ON {_table('billing_summary')} (generated_at)"
    )


def downgrade() -> None:
    pass
