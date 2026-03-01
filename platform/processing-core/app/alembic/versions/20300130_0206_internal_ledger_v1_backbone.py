"""Internal Ledger v1 backbone tables and invariants.

Revision ID: 20300130_0206_internal_ledger_v1_backbone
Revises: 20300120_0205_merge_heads
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import SCHEMA, is_postgres

revision = "20300130_0206_internal_ledger_v1_backbone"
down_revision = "20300120_0205_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "internal_ledger_v1_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_code", sa.Text(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column("owner_type", sa.Text(), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
        sa.Column("status", sa.Text(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_code", name="uq_ilv1_accounts_code"),
        schema=SCHEMA,
    )
    op.create_index("ix_ilv1_accounts_owner", "internal_ledger_v1_accounts", ["owner_type", "owner_id"], schema=SCHEMA)
    op.create_index("ix_ilv1_accounts_currency", "internal_ledger_v1_accounts", ["currency"], schema=SCHEMA)

    op.create_table(
        "internal_ledger_v1_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("entry_type", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("source_system", sa.Text(), nullable=False, server_default="core-api"),
        sa.Column("source_event_id", sa.Text(), nullable=True),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq_ilv1_entries_idempotency"),
        schema=SCHEMA,
    )
    op.create_index("ix_ilv1_entries_correlation", "internal_ledger_v1_entries", ["correlation_id"], schema=SCHEMA)
    op.create_index("ix_ilv1_entries_dimensions", "internal_ledger_v1_entries", ["dimensions"], schema=SCHEMA, postgresql_using="gin")

    op.create_table(
        "internal_ledger_v1_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.internal_ledger_v1_entries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.internal_ledger_v1_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.UniqueConstraint("entry_id", "line_no", name="uq_ilv1_lines_entry_line_no"),
        sa.CheckConstraint("amount > 0", name="ck_ilv1_lines_amount_positive"),
        schema=SCHEMA,
    )
    op.create_index("ix_ilv1_lines_entry", "internal_ledger_v1_lines", ["entry_id"], schema=SCHEMA)
    op.create_index("ix_ilv1_lines_account", "internal_ledger_v1_lines", ["account_id"], schema=SCHEMA)

    op.create_table(
        "internal_ledger_v1_account_balances",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.internal_ledger_v1_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("account_id", "currency", name="pk_ilv1_account_balances"),
        schema=SCHEMA,
    )

    bind = op.get_bind()
    if is_postgres(bind):
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {SCHEMA}.ilv1_prevent_entry_mutation()
            RETURNS trigger AS $$
            BEGIN
              IF OLD.status = 'POSTED' THEN
                RAISE EXCEPTION 'posted entries are immutable';
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {SCHEMA}.ilv1_prevent_line_mutation()
            RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'ledger lines are immutable';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"CREATE TRIGGER ilv1_entries_no_update BEFORE UPDATE ON {SCHEMA}.internal_ledger_v1_entries FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.ilv1_prevent_entry_mutation();"
        )
        op.execute(
            f"CREATE TRIGGER ilv1_entries_no_delete BEFORE DELETE ON {SCHEMA}.internal_ledger_v1_entries FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.ilv1_prevent_entry_mutation();"
        )
        op.execute(
            f"CREATE TRIGGER ilv1_lines_no_update BEFORE UPDATE ON {SCHEMA}.internal_ledger_v1_lines FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.ilv1_prevent_line_mutation();"
        )
        op.execute(
            f"CREATE TRIGGER ilv1_lines_no_delete BEFORE DELETE ON {SCHEMA}.internal_ledger_v1_lines FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.ilv1_prevent_line_mutation();"
        )
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {SCHEMA}.ilv1_assert_balanced()
            RETURNS trigger AS $$
            DECLARE
              debit_sum numeric(18,2);
              credit_sum numeric(18,2);
              target_entry uuid;
            BEGIN
              target_entry := COALESCE(NEW.entry_id, OLD.entry_id);
              SELECT COALESCE(SUM(CASE WHEN direction='DEBIT' THEN amount ELSE 0 END),0),
                     COALESCE(SUM(CASE WHEN direction='CREDIT' THEN amount ELSE 0 END),0)
                INTO debit_sum, credit_sum
              FROM {SCHEMA}.internal_ledger_v1_lines
              WHERE entry_id = target_entry;
              IF debit_sum <> credit_sum THEN
                RAISE EXCEPTION 'entry lines are unbalanced';
              END IF;
              RETURN NULL;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"""
            CREATE CONSTRAINT TRIGGER ilv1_balance_on_commit
            AFTER INSERT OR UPDATE OR DELETE ON {SCHEMA}.internal_ledger_v1_lines
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.ilv1_assert_balanced();
            """
        )


def downgrade() -> None:
    pass
