"""Phase 3 financial hardening and tamper evidence

Revision ID: 20299990_0189_phase3_financial_hardening
Revises: 20299810_0184_event_outbox
Create Date: 2029-12-31 00:18:90.000000
"""

from alembic import op
import sqlalchemy as sa

from alembic_helpers import SCHEMA, is_postgres


revision = "20299990_0189_phase3_financial_hardening"
down_revision = "20299810_0184_event_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("internal_ledger_transactions", sa.Column("total_debit", sa.BigInteger(), nullable=False, server_default="0"), schema=SCHEMA)
    op.add_column("internal_ledger_transactions", sa.Column("total_credit", sa.BigInteger(), nullable=False, server_default="0"), schema=SCHEMA)
    op.add_column("internal_ledger_transactions", sa.Column("batch_sequence", sa.BigInteger(), nullable=False, server_default="0"), schema=SCHEMA)
    op.add_column("internal_ledger_transactions", sa.Column("previous_batch_hash", sa.String(length=64), nullable=False, server_default="GENESIS_INTERNAL_LEDGER_V1"), schema=SCHEMA)
    op.add_column("internal_ledger_transactions", sa.Column("batch_hash", sa.String(length=64), nullable=False, server_default=""), schema=SCHEMA)
    op.create_unique_constraint("uq_internal_ledger_batch_sequence", "internal_ledger_transactions", ["tenant_id", "batch_sequence"], schema=SCHEMA)
    op.create_check_constraint("ck_internal_ledger_transaction_balanced", "internal_ledger_transactions", "total_debit = total_credit", schema=SCHEMA)

    op.add_column("settlement_periods", sa.Column("genesis_batch_hash", sa.String(length=64), nullable=False, server_default="GENESIS_INTERNAL_LEDGER_V1"), schema=SCHEMA)
    op.add_column("settlement_periods", sa.Column("last_batch_hash", sa.String(length=64), nullable=True), schema=SCHEMA)
    op.add_column("settlement_periods", sa.Column("period_hash", sa.String(length=64), nullable=True), schema=SCHEMA)
    op.add_column("settlement_periods", sa.Column("snapshot_payload", sa.JSON(), nullable=True), schema=SCHEMA)

    op.add_column("invoice_payments", sa.Column("response_hash", sa.String(length=64), nullable=False, server_default=""), schema=SCHEMA)
    op.add_column("credit_notes", sa.Column("response_hash", sa.String(length=64), nullable=False, server_default=""), schema=SCHEMA)

    op.create_table(
        "reconciliation_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("report_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("ix_reconciliation_reports_created", "reconciliation_reports", ["created_at"], schema=SCHEMA)

    if is_postgres(bind):
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {SCHEMA}.prevent_ledger_mutation()
            RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'Ledger entries are immutable';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER ledger_no_update
            BEFORE UPDATE ON {SCHEMA}.internal_ledger_entries
            FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.prevent_ledger_mutation();
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER ledger_no_delete
            BEFORE DELETE ON {SCHEMA}.internal_ledger_entries
            FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.prevent_ledger_mutation();
            """
        )

        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {SCHEMA}.prevent_idempotency_mutation()
            RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'Idempotency records are immutable';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        for table in ("invoice_payments", "credit_notes", "payouts"):
            op.execute(
                f"""
                CREATE TRIGGER {table}_no_update
                BEFORE UPDATE ON {SCHEMA}.{table}
                FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.prevent_idempotency_mutation();
                """
            )
            op.execute(
                f"""
                CREATE TRIGGER {table}_no_delete
                BEFORE DELETE ON {SCHEMA}.{table}
                FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.prevent_idempotency_mutation();
                """
            )


def downgrade() -> None:
    pass
