"""Fleet offline tables runtime repair.

Revision ID: 20300330_0226_fleet_offline_tables_runtime_repair
Revises: 20300320_0225_client_docflow_notification_compat_defaults
Create Date: 2026-04-21 22:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    column_exists,
    constraint_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_pg_enum_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
    table_exists,
)
from db.types import GUID


revision = "20300330_0226_fleet_offline_tables_runtime_repair"
down_revision = "20300320_0225_client_docflow_notification_compat_defaults"
branch_labels = None
depends_on = None


PROFILE_STATUSES = ["ACTIVE", "INACTIVE"]
RECONCILIATION_STATUSES = ["STARTED", "FINISHED", "FAILED"]
DISCREPANCY_REASONS = [
    "OFFLINE_LIMIT_EXCEEDED",
    "UNEXPECTED_PRODUCT",
    "CARD_BLOCKED_AT_TIME",
    "DUPLICATE_TX",
    "AMOUNT_MISMATCH",
]


def _fk(target: str) -> str:
    return f"{DB_SCHEMA}.{target}" if DB_SCHEMA else target


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "fleet_offline_profile_status", PROFILE_STATUSES, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "fleet_offline_reconciliation_status", RECONCILIATION_STATUSES, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "fleet_offline_discrepancy_reason", DISCREPANCY_REASONS, schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "fleet_offline_profiles",
        schema=DB_SCHEMA,
        columns=(
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("client_id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("daily_amount_limit", sa.Numeric(), nullable=True),
            sa.Column("daily_txn_limit", sa.Integer(), nullable=True),
            sa.Column("allowed_products", sa.JSON(), nullable=True),
            sa.Column("allowed_stations", sa.JSON(), nullable=True),
            sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "status",
                safe_enum(bind, "fleet_offline_profile_status", PROFILE_STATUSES, schema=DB_SCHEMA),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        ),
    )
    create_index_if_not_exists(
        bind,
        "ix_fleet_offline_profiles_client_id",
        "fleet_offline_profiles",
        ["client_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fleet_offline_profiles_client_status",
        "fleet_offline_profiles",
        ["client_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "fleet_offline_reconciliation_runs",
        schema=DB_SCHEMA,
        columns=(
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("client_id", sa.String(length=64), nullable=False),
            sa.Column("period_key", sa.String(length=32), nullable=False),
            sa.Column(
                "status",
                safe_enum(bind, "fleet_offline_reconciliation_status", RECONCILIATION_STATUSES, schema=DB_SCHEMA),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        ),
    )
    create_index_if_not_exists(
        bind,
        "ix_fleet_offline_reconciliation_runs_client_id",
        "fleet_offline_reconciliation_runs",
        ["client_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fleet_offline_reconciliation_client_period",
        "fleet_offline_reconciliation_runs",
        ["client_id", "period_key"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "fleet_offline_discrepancies",
        schema=DB_SCHEMA,
        columns=(
            sa.Column("id", GUID(), primary_key=True),
            sa.Column(
                "run_id",
                GUID(),
                sa.ForeignKey(_fk("fleet_offline_reconciliation_runs.id"), ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("provider_tx_id", sa.String(length=128), nullable=True),
            sa.Column("tx_id", sa.String(length=36), nullable=True),
            sa.Column(
                "reason",
                safe_enum(bind, "fleet_offline_discrepancy_reason", DISCREPANCY_REASONS, schema=DB_SCHEMA),
                nullable=False,
            ),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        ),
    )
    create_index_if_not_exists(
        bind,
        "ix_fleet_offline_discrepancies_run",
        "fleet_offline_discrepancies",
        ["run_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fleet_offline_discrepancies_provider_tx_id",
        "fleet_offline_discrepancies",
        ["provider_tx_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fleet_offline_discrepancies_tx_id",
        "fleet_offline_discrepancies",
        ["tx_id"],
        schema=DB_SCHEMA,
    )

    if table_exists(bind, "fuel_cards", schema=DB_SCHEMA) and not column_exists(
        bind, "fuel_cards", "card_offline_profile_id", schema=DB_SCHEMA
    ):
        op.add_column("fuel_cards", sa.Column("card_offline_profile_id", GUID(), nullable=True), schema=DB_SCHEMA)
        create_index_if_not_exists(
            bind,
            "ix_fuel_cards_card_offline_profile_id",
            "fuel_cards",
            ["card_offline_profile_id"],
            schema=DB_SCHEMA,
        )
    if (
        table_exists(bind, "fuel_cards", schema=DB_SCHEMA)
        and not constraint_exists(bind, "fuel_cards", "fk_fuel_cards_card_offline_profile_id", schema=DB_SCHEMA)
    ):
        op.create_foreign_key(
            "fk_fuel_cards_card_offline_profile_id",
            "fuel_cards",
            "fleet_offline_profiles",
            ["card_offline_profile_id"],
            ["id"],
            source_schema=DB_SCHEMA,
            referent_schema=DB_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "fuel_cards", schema=DB_SCHEMA):
        if constraint_exists(bind, "fuel_cards", "fk_fuel_cards_card_offline_profile_id", schema=DB_SCHEMA):
            op.drop_constraint("fk_fuel_cards_card_offline_profile_id", "fuel_cards", schema=DB_SCHEMA, type_="foreignkey")
        if column_exists(bind, "fuel_cards", "card_offline_profile_id", schema=DB_SCHEMA):
            op.drop_column("fuel_cards", "card_offline_profile_id", schema=DB_SCHEMA)

    drop_table_if_exists(bind, "fleet_offline_discrepancies", schema=DB_SCHEMA)
    drop_table_if_exists(bind, "fleet_offline_reconciliation_runs", schema=DB_SCHEMA)
    drop_table_if_exists(bind, "fleet_offline_profiles", schema=DB_SCHEMA)
    drop_pg_enum_if_exists(bind, "fleet_offline_discrepancy_reason", schema=DB_SCHEMA)
    drop_pg_enum_if_exists(bind, "fleet_offline_reconciliation_status", schema=DB_SCHEMA)
    drop_pg_enum_if_exists(bind, "fleet_offline_profile_status", schema=DB_SCHEMA)
