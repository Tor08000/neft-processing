"""Marketplace contracts and SLA v1.

Revision ID: 20291940_0102_marketplace_contracts_v1
Revises: 20291930_0101_settlement_v1
Create Date: 2025-03-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from app.alembic.utils import (
    SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    is_postgres,
    table_exists,
)
from app.db.types import GUID


revision = "20291940_0102_marketplace_contracts_v1"
down_revision = "20291930_0101_settlement_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _schema_prefix() -> str:
    return f"{SCHEMA}." if SCHEMA else ""


def _create_worm_trigger(table_name: str) -> None:
    if not is_postgres(op.get_bind()):
        return
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION '{table_name} is WORM';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DROP TRIGGER IF EXISTS {table_name}_worm_update
            ON {_schema_prefix()}{table_name}
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {table_name}_worm_update
            BEFORE UPDATE ON {_schema_prefix()}{table_name}
            FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DROP TRIGGER IF EXISTS {table_name}_worm_delete
            ON {_schema_prefix()}{table_name}
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {table_name}_worm_delete
            BEFORE DELETE ON {_schema_prefix()}{table_name}
            FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}{table_name}_worm_guard()
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_not_exists(
        bind,
        "contracts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("contract_number", sa.String(length=64), nullable=False),
        sa.Column("contract_type", sa.String(length=32), nullable=False),
        sa.Column("party_a_type", sa.String(length=32), nullable=False),
        sa.Column("party_a_id", GUID(), nullable=False),
        sa.Column("party_b_type", sa.String(length=32), nullable=False),
        sa.Column("party_b_id", GUID(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("audit_event_id", GUID(), nullable=False),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_contracts_number",
        "contracts",
        ["contract_number"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "contract_versions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("contract_id", GUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("terms", JSON_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("audit_event_id", GUID(), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_contract_versions_contract_id",
        "contract_versions",
        ["contract_id"],
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_contract_versions_version",
        "contract_versions",
        ["contract_id", "version"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "contract_obligations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("contract_id", GUID(), nullable=False),
        sa.Column("obligation_type", sa.String(length=32), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 4), nullable=False),
        sa.Column("comparison", sa.String(length=8), nullable=False),
        sa.Column("window", sa.String(length=32), nullable=True),
        sa.Column("penalty_type", sa.String(length=16), nullable=False),
        sa.Column("penalty_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_contract_obligations_contract_id",
        "contract_obligations",
        ["contract_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "contract_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("contract_id", GUID(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", JSON_TYPE, nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.String(length=512), nullable=True),
        sa.Column("signature_alg", sa.String(length=64), nullable=True),
        sa.Column("signing_key_id", sa.String(length=128), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_event_id", GUID(), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_contract_events_contract_id",
        "contract_events",
        ["contract_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_contract_events_occurred_at",
        "contract_events",
        ["occurred_at"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "sla_results",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("contract_id", GUID(), nullable=False),
        sa.Column("obligation_id", GUID(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("measured_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("audit_event_id", GUID(), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_sla_results_contract_id",
        "sla_results",
        ["contract_id"],
        schema=SCHEMA,
    )

    if table_exists(bind, "contracts", schema=SCHEMA):
        _create_worm_trigger("contracts")
    if table_exists(bind, "contract_versions", schema=SCHEMA):
        _create_worm_trigger("contract_versions")
    if table_exists(bind, "contract_events", schema=SCHEMA):
        _create_worm_trigger("contract_events")


def downgrade() -> None:
    pass
