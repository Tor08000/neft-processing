"""Separate demo subscription seed from commercial tariff codes.

Revision ID: 20300290_0222_subscription_plan_demo_seed_runtime_repair
Revises: 20300280_0221_billing_summary_audit_columns_runtime_repair
Create Date: 2030-01-20 03:30:00.000000
"""

from __future__ import annotations

from alembic import op

from db.schema import resolve_db_schema


revision = "20300290_0222_subscription_plan_demo_seed_runtime_repair"
down_revision = "20300280_0221_billing_summary_audit_columns_runtime_repair"
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
        f"""
        UPDATE {_table('subscription_plans')}
        SET price_cents = 9900,
            discount_percent = 0,
            billing_period_months = 1,
            is_active = TRUE
        WHERE code = 'CONTROL_INDIVIDUAL_1M'
          AND COALESCE(price_cents, 0) = 0
          AND lower(COALESCE(title, '')) LIKE 'control individual%%';
        """
    )


def downgrade() -> None:
    pass
