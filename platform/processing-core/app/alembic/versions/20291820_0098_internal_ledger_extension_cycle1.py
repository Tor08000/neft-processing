"""Internal ledger cycle 1 extensions.

Revision ID: 20291820_0098_internal_ledger_extension_cycle1
Revises: 20291810_0097_decision_memory_audit
Create Date: 2025-03-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.helpers import column_exists, is_postgres, table_exists
from app.db.schema import resolve_db_schema


revision = "20291820_0098_internal_ledger_extension_cycle1"
down_revision = "20291810_0097_decision_memory_audit"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _schema_prefix() -> str:
    return f"{SCHEMA}." if SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "internal_ledger_transactions", schema=SCHEMA):
        if not column_exists(bind, "internal_ledger_transactions", "total_amount", schema=SCHEMA):
            op.add_column(
                "internal_ledger_transactions",
                sa.Column("total_amount", sa.BigInteger(), nullable=True),
                schema=SCHEMA,
            )
        if not column_exists(bind, "internal_ledger_transactions", "currency", schema=SCHEMA):
            op.add_column(
                "internal_ledger_transactions",
                sa.Column("currency", sa.String(length=3), nullable=True),
                schema=SCHEMA,
            )

    if is_postgres(bind) and table_exists(bind, "internal_ledger_entries", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}internal_ledger_entries_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'internal_ledger_entries is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS internal_ledger_entries_worm_update ON {_schema_prefix()}internal_ledger_entries;
                CREATE TRIGGER internal_ledger_entries_worm_update
                BEFORE UPDATE ON {_schema_prefix()}internal_ledger_entries
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}internal_ledger_entries_worm_guard();
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS internal_ledger_entries_worm_delete ON {_schema_prefix()}internal_ledger_entries;
                CREATE TRIGGER internal_ledger_entries_worm_delete
                BEFORE DELETE ON {_schema_prefix()}internal_ledger_entries
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}internal_ledger_entries_worm_guard();
                """
            )
        )

    if is_postgres(bind) and table_exists(bind, "internal_ledger_transactions", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}internal_ledger_transactions_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'internal_ledger_transactions is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS internal_ledger_transactions_worm_update
                ON {_schema_prefix()}internal_ledger_transactions;
                CREATE TRIGGER internal_ledger_transactions_worm_update
                BEFORE UPDATE ON {_schema_prefix()}internal_ledger_transactions
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}internal_ledger_transactions_worm_guard();
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS internal_ledger_transactions_worm_delete
                ON {_schema_prefix()}internal_ledger_transactions;
                CREATE TRIGGER internal_ledger_transactions_worm_delete
                BEFORE DELETE ON {_schema_prefix()}internal_ledger_transactions
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}internal_ledger_transactions_worm_guard();
                """
            )
        )


def downgrade() -> None:
    pass
