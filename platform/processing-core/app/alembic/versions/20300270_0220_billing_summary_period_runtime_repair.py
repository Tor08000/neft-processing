"""Repair billing_summary period linkage expected by runtime seed/billing flows.

Revision ID: 20300270_0220_billing_summary_period_runtime_repair
Revises: 20300260_0219_marketplace_adjustments_runtime_repair
Create Date: 2030-01-20 03:00:00.000000
"""

from __future__ import annotations

from alembic import op

from db.schema import resolve_db_schema


revision = "20300270_0220_billing_summary_period_runtime_repair"
down_revision = "20300260_0219_marketplace_adjustments_runtime_repair"
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
        "ADD COLUMN IF NOT EXISTS billing_period_id UUID NULL"
    )
    bind.exec_driver_sql(
        f"CREATE INDEX IF NOT EXISTS ix_billing_summary_billing_period_id "
        f"ON {_table('billing_summary')} (billing_period_id)"
    )
    bind.exec_driver_sql(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_billing_summary_billing_period_id'
                  AND conrelid = '{_table('billing_summary')}'::regclass
            ) THEN
                ALTER TABLE {_table('billing_summary')}
                ADD CONSTRAINT fk_billing_summary_billing_period_id
                FOREIGN KEY (billing_period_id)
                REFERENCES {_table('billing_periods')}(id)
                NOT VALID;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    pass
