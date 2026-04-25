"""Add PDF artifact columns to billing flow invoices.

Revision ID: 20300310_0224_billing_invoice_pdf_artifact_repair
Revises: 20300300_0223_card_access_runtime_repair
Create Date: 2030-01-20 04:20:00.000000
"""

from __future__ import annotations

from alembic import op

from db.schema import resolve_db_schema


revision = "20300310_0224_billing_invoice_pdf_artifact_repair"
down_revision = "20300300_0223_card_access_runtime_repair"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _table(name: str) -> str:
    return f"{_q(SCHEMA)}.{_q(name)}" if SCHEMA else _q(name)


def _schema_prefix() -> str:
    return f"{_q(SCHEMA)}." if SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(f"ALTER TABLE {_table('billing_invoices')} ADD COLUMN IF NOT EXISTS pdf_status VARCHAR(32) NOT NULL DEFAULT 'NONE';")
    bind.exec_driver_sql(f"ALTER TABLE {_table('billing_invoices')} ADD COLUMN IF NOT EXISTS pdf_object_key VARCHAR(512);")
    bind.exec_driver_sql(f"ALTER TABLE {_table('billing_invoices')} ADD COLUMN IF NOT EXISTS pdf_url VARCHAR(512);")
    bind.exec_driver_sql(f"ALTER TABLE {_table('billing_invoices')} ADD COLUMN IF NOT EXISTS pdf_hash VARCHAR(64);")
    bind.exec_driver_sql(f"ALTER TABLE {_table('billing_invoices')} ADD COLUMN IF NOT EXISTS pdf_generated_at TIMESTAMPTZ;")
    bind.exec_driver_sql(f"CREATE INDEX IF NOT EXISTS ix_billing_invoices_pdf_status ON {_table('billing_invoices')} (pdf_status);")

    if bind.dialect.name != "postgresql":
        return

    bind.exec_driver_sql(
        f"""
        CREATE OR REPLACE FUNCTION {_schema_prefix()}billing_invoices_worm_guard()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status
                OR NEW.amount_paid IS DISTINCT FROM OLD.amount_paid
                OR NEW.pdf_status IS DISTINCT FROM OLD.pdf_status
                OR NEW.pdf_object_key IS DISTINCT FROM OLD.pdf_object_key
                OR NEW.pdf_url IS DISTINCT FROM OLD.pdf_url
                OR NEW.pdf_hash IS DISTINCT FROM OLD.pdf_hash
                OR NEW.pdf_generated_at IS DISTINCT FROM OLD.pdf_generated_at THEN
                IF NEW.invoice_number IS DISTINCT FROM OLD.invoice_number
                    OR NEW.client_id IS DISTINCT FROM OLD.client_id
                    OR NEW.case_id IS DISTINCT FROM OLD.case_id
                    OR NEW.currency IS DISTINCT FROM OLD.currency
                    OR NEW.amount_total IS DISTINCT FROM OLD.amount_total
                    OR NEW.issued_at IS DISTINCT FROM OLD.issued_at
                    OR NEW.due_at IS DISTINCT FROM OLD.due_at
                    OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
                    OR NEW.ledger_tx_id IS DISTINCT FROM OLD.ledger_tx_id
                    OR NEW.audit_event_id IS DISTINCT FROM OLD.audit_event_id
                    OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                    RAISE EXCEPTION 'billing_invoices is WORM';
                END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'billing_invoices is WORM';
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    pass
