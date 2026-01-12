"""Reconciliation runs, discrepancies, and external statements.

Revision ID: 20291910_0099_reconciliation_v1
Revises: 20291820_0098_internal_ledger_extension_cycle1
Create Date: 2025-03-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from alembic_helpers import (
    SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    is_postgres,
    safe_enum,
    table_exists,
)
from db.types import GUID


revision = "20291910_0099_reconciliation_v1"
down_revision = "20291820_0098_internal_ledger_extension_cycle1"
branch_labels = None
depends_on = None


RECONCILIATION_SCOPE = ["internal", "external"]
RECONCILIATION_RUN_STATUS = ["started", "completed", "failed"]
RECONCILIATION_DISCREPANCY_TYPE = [
    "balance_mismatch",
    "missing_entry",
    "duplicate_entry",
    "unmatched_external",
    "unmatched_internal",
    "fx_not_supported",
]
RECONCILIATION_DISCREPANCY_STATUS = ["open", "resolved", "ignored"]

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _schema_prefix() -> str:
    return f"{SCHEMA}." if SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "reconciliation_run_scope", RECONCILIATION_SCOPE, schema=SCHEMA)
    ensure_pg_enum(bind, "reconciliation_run_status", RECONCILIATION_RUN_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "reconciliation_discrepancy_type", RECONCILIATION_DISCREPANCY_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "reconciliation_discrepancy_status", RECONCILIATION_DISCREPANCY_STATUS, schema=SCHEMA)
    ensure_pg_enum_value(bind, "internal_ledger_transaction_type", "ADJUSTMENT", schema=SCHEMA)

    if not table_exists(bind, "reconciliation_runs", schema=SCHEMA):
        scope_enum = safe_enum(bind, "reconciliation_run_scope", RECONCILIATION_SCOPE, schema=SCHEMA)
        status_enum = safe_enum(bind, "reconciliation_run_status", RECONCILIATION_RUN_STATUS, schema=SCHEMA)
        create_table_if_not_exists(
            bind,
            "reconciliation_runs",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("scope", scope_enum, nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=True),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", status_enum, nullable=False, server_default=RECONCILIATION_RUN_STATUS[0]),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by_user_id", GUID(), nullable=True),
            sa.Column("summary", JSON_TYPE, nullable=True),
            sa.Column("audit_event_id", GUID(), nullable=True),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_reconciliation_runs_scope_created",
            "reconciliation_runs",
            ["scope", "created_at"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_reconciliation_runs_provider_created",
            "reconciliation_runs",
            ["provider", "created_at"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "reconciliation_discrepancies", schema=SCHEMA):
        type_enum = safe_enum(
            bind, "reconciliation_discrepancy_type", RECONCILIATION_DISCREPANCY_TYPE, schema=SCHEMA
        )
        status_enum = safe_enum(
            bind, "reconciliation_discrepancy_status", RECONCILIATION_DISCREPANCY_STATUS, schema=SCHEMA
        )
        create_table_if_not_exists(
            bind,
            "reconciliation_discrepancies",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("run_id", GUID(), nullable=False),
            sa.Column("ledger_account_id", GUID(), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("discrepancy_type", type_enum, nullable=False),
            sa.Column("internal_amount", sa.Numeric(18, 4), nullable=True),
            sa.Column("external_amount", sa.Numeric(18, 4), nullable=True),
            sa.Column("delta", sa.Numeric(18, 4), nullable=True),
            sa.Column("details", JSON_TYPE, nullable=True),
            sa.Column("status", status_enum, nullable=False, server_default=RECONCILIATION_DISCREPANCY_STATUS[0]),
            sa.Column("resolution", JSON_TYPE, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["run_id"], [f"{SCHEMA}.reconciliation_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["ledger_account_id"], [f"{SCHEMA}.internal_ledger_accounts.id"]),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_reconciliation_discrepancies_run_status",
            "reconciliation_discrepancies",
            ["run_id", "status"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_reconciliation_discrepancies_account_created",
            "reconciliation_discrepancies",
            ["ledger_account_id", "created_at"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "external_statements", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "external_statements",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("total_in", sa.Numeric(18, 4), nullable=True),
            sa.Column("total_out", sa.Numeric(18, 4), nullable=True),
            sa.Column("closing_balance", sa.Numeric(18, 4), nullable=True),
            sa.Column("lines", JSON_TYPE, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("source_hash", sa.String(length=64), nullable=False),
            sa.Column("audit_event_id", GUID(), nullable=True),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_external_statements_provider_period",
            "external_statements",
            ["provider", "period_end"],
            schema=SCHEMA,
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_external_statements_source",
            "external_statements",
            ["provider", "source_hash"],
            schema=SCHEMA,
        )

    if not is_postgres(bind):
        return

    if table_exists(bind, "external_statements", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}external_statements_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'external_statements is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS external_statements_worm_update
                ON {_schema_prefix()}external_statements
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER external_statements_worm_update
                BEFORE UPDATE ON {_schema_prefix()}external_statements
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}external_statements_worm_guard()
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS external_statements_worm_delete
                ON {_schema_prefix()}external_statements
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER external_statements_worm_delete
                BEFORE DELETE ON {_schema_prefix()}external_statements
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}external_statements_worm_guard()
                """
            )
        )

    if table_exists(bind, "reconciliation_runs", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}reconciliation_runs_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.scope IS DISTINCT FROM OLD.scope
                        OR NEW.provider IS DISTINCT FROM OLD.provider
                        OR NEW.period_start IS DISTINCT FROM OLD.period_start
                        OR NEW.period_end IS DISTINCT FROM OLD.period_end
                        OR NEW.created_at IS DISTINCT FROM OLD.created_at
                        OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id THEN
                        RAISE EXCEPTION 'reconciliation_runs is WORM';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS reconciliation_runs_worm_update
                ON {_schema_prefix()}reconciliation_runs
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER reconciliation_runs_worm_update
                BEFORE UPDATE ON {_schema_prefix()}reconciliation_runs
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}reconciliation_runs_worm_guard()
                """
            )
        )

    if table_exists(bind, "reconciliation_discrepancies", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}reconciliation_discrepancies_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.run_id IS DISTINCT FROM OLD.run_id
                        OR NEW.ledger_account_id IS DISTINCT FROM OLD.ledger_account_id
                        OR NEW.currency IS DISTINCT FROM OLD.currency
                        OR NEW.discrepancy_type IS DISTINCT FROM OLD.discrepancy_type
                        OR NEW.internal_amount IS DISTINCT FROM OLD.internal_amount
                        OR NEW.external_amount IS DISTINCT FROM OLD.external_amount
                        OR NEW.delta IS DISTINCT FROM OLD.delta
                        OR NEW.details IS DISTINCT FROM OLD.details
                        OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                        RAISE EXCEPTION 'reconciliation_discrepancies is WORM';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS reconciliation_discrepancies_worm_update
                ON {_schema_prefix()}reconciliation_discrepancies
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER reconciliation_discrepancies_worm_update
                BEFORE UPDATE ON {_schema_prefix()}reconciliation_discrepancies
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}reconciliation_discrepancies_worm_guard()
                """
            )
        )


def downgrade() -> None:
    pass
