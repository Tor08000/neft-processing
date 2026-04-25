"""fuel domain v2 hardening

Revision ID: 20291320_0061_fuel_hardening_v2
Revises: 20291320_0060_fuel_domain_v2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import column_exists, constraint_exists, create_index_if_not_exists, create_table_if_not_exists
from db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20291320_0061_fuel_hardening_v2"
down_revision = "20291320_0060_fuel_domain_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("fuel_transactions", schema=SCHEMA) as batch_op:
        if not column_exists(bind, "fuel_transactions", "external_settlement_ref", schema=SCHEMA):
            batch_op.add_column(sa.Column("external_settlement_ref", sa.String(length=128), nullable=True))
        if not column_exists(bind, "fuel_transactions", "external_reverse_ref", schema=SCHEMA):
            batch_op.add_column(sa.Column("external_reverse_ref", sa.String(length=128), nullable=True))
        if not constraint_exists(bind, "fuel_transactions", "uq_fuel_transactions_tenant_network_external_ref", schema=SCHEMA):
            batch_op.create_unique_constraint(
                "uq_fuel_transactions_tenant_network_external_ref",
                ["tenant_id", "network_id", "external_ref"],
            )
        if not constraint_exists(bind, "fuel_transactions", "uq_fuel_transactions_settlement_ref", schema=SCHEMA):
            batch_op.create_unique_constraint(
                "uq_fuel_transactions_settlement_ref",
                ["id", "external_settlement_ref"],
            )
        if not constraint_exists(bind, "fuel_transactions", "uq_fuel_transactions_reverse_ref", schema=SCHEMA):
            batch_op.create_unique_constraint(
                "uq_fuel_transactions_reverse_ref",
                ["id", "external_reverse_ref"],
            )

    create_table_if_not_exists(
        bind,
        "fuel_analytics_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("fuel_tx_id", sa.String(length=36), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("explain", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fuel_tx_id"], [f"{SCHEMA}.fuel_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fuel_analytics_events_fuel_tx_id",
        "fuel_analytics_events",
        ["fuel_tx_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_fuel_analytics_events_fuel_tx_id", table_name="fuel_analytics_events", schema=SCHEMA)
    op.drop_table("fuel_analytics_events", schema=SCHEMA)
    with op.batch_alter_table("fuel_transactions", schema=SCHEMA) as batch_op:
        batch_op.drop_constraint("uq_fuel_transactions_reverse_ref", type_="unique")
        batch_op.drop_constraint("uq_fuel_transactions_settlement_ref", type_="unique")
        batch_op.drop_constraint("uq_fuel_transactions_tenant_network_external_ref", type_="unique")
        batch_op.drop_column("external_reverse_ref")
        batch_op.drop_column("external_settlement_ref")
