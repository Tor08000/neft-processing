"""Billing flows v1 models and reconciliation links.

Revision ID: 20291920_0100_billing_flows_v1
Revises: 20291910_0099_reconciliation_v1
Create Date: 2025-03-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from app.alembic.utils import (
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
from app.db.types import GUID


revision = "20291920_0100_billing_flows_v1"
down_revision = "20291910_0099_reconciliation_v1"
branch_labels = None
depends_on = None


BILLING_INVOICE_STATUS = ["ISSUED", "PARTIALLY_PAID", "PAID", "VOID"]
BILLING_PAYMENT_STATUS = ["CAPTURED", "FAILED", "REFUNDED_PARTIAL", "REFUNDED_FULL"]
BILLING_REFUND_STATUS = ["REFUNDED", "FAILED"]
RECONCILIATION_LINK_DIRECTION = ["IN", "OUT"]
RECONCILIATION_LINK_STATUS = ["pending", "matched", "mismatched"]


def _schema_prefix() -> str:
    if not SCHEMA:
        return ""
    return f"{SCHEMA}."


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "billing_invoice_status", BILLING_INVOICE_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "billing_payment_status", BILLING_PAYMENT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "billing_refund_status", BILLING_REFUND_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "reconciliation_link_direction", RECONCILIATION_LINK_DIRECTION, schema=SCHEMA)
    ensure_pg_enum(bind, "reconciliation_link_status", RECONCILIATION_LINK_STATUS, schema=SCHEMA)

    ensure_pg_enum_value(bind, "case_event_type", "INVOICE_ISSUED", schema=SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "PAYMENT_CAPTURED", schema=SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "PAYMENT_REFUNDED", schema=SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "INVOICE_STATUS_CHANGED", schema=SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "EXTERNAL_RECONCILIATION_COMPLETED", schema=SCHEMA)
    ensure_pg_enum_value(bind, "reconciliation_discrepancy_type", "mismatched_amount", schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "billing_invoices",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("case_id", GUID(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("amount_total", sa.Numeric(18, 4), nullable=False),
        sa.Column("amount_paid", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column(
            "status",
            safe_enum(bind, "billing_invoice_status", BILLING_INVOICE_STATUS, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("ledger_tx_id", GUID(), nullable=False),
        sa.Column("audit_event_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_billing_invoices_number",
        "billing_invoices",
        ["invoice_number"],
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_billing_invoices_idempotency",
        "billing_invoices",
        ["idempotency_key"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_billing_invoices_client_status",
        "billing_invoices",
        ["client_id", "status"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "billing_payments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("invoice_id", GUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=128), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            safe_enum(bind, "billing_payment_status", BILLING_PAYMENT_STATUS, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("ledger_tx_id", GUID(), nullable=False),
        sa.Column("external_statement_line_id", sa.String(length=128), nullable=True),
        sa.Column("audit_event_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["invoice_id"], [f"{_schema_prefix()}billing_invoices.id"], ondelete="CASCADE"),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_billing_payments_idempotency",
        "billing_payments",
        ["idempotency_key"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_billing_payments_invoice",
        "billing_payments",
        ["invoice_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "billing_refunds",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("payment_id", GUID(), nullable=False),
        sa.Column("provider_refund_id", sa.String(length=128), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            safe_enum(bind, "billing_refund_status", BILLING_REFUND_STATUS, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("ledger_tx_id", GUID(), nullable=False),
        sa.Column("external_statement_line_id", sa.String(length=128), nullable=True),
        sa.Column("audit_event_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["payment_id"], [f"{_schema_prefix()}billing_payments.id"], ondelete="CASCADE"),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_billing_refunds_idempotency",
        "billing_refunds",
        ["idempotency_key"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_billing_refunds_payment",
        "billing_refunds",
        ["payment_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "reconciliation_links",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", GUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("expected_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "direction",
            safe_enum(
                bind,
                "reconciliation_link_direction",
                RECONCILIATION_LINK_DIRECTION,
                schema=SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("expected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("match_key", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            safe_enum(bind, "reconciliation_link_status", RECONCILIATION_LINK_STATUS, schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("run_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["run_id"], [f"{_schema_prefix()}reconciliation_runs.id"], ondelete="SET NULL"),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_reconciliation_link_entity",
        "reconciliation_links",
        ["entity_type", "entity_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_reconciliation_links_provider_status_expected",
        "reconciliation_links",
        ["provider", "status", "expected_at"],
        schema=SCHEMA,
    )

    if not is_postgres(bind):
        return

    if table_exists(bind, "billing_invoices", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}billing_invoices_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.status IS DISTINCT FROM OLD.status
                        OR NEW.amount_paid IS DISTINCT FROM OLD.amount_paid THEN
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
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS billing_invoices_worm_update
                ON {_schema_prefix()}billing_invoices
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER billing_invoices_worm_update
                BEFORE UPDATE ON {_schema_prefix()}billing_invoices
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}billing_invoices_worm_guard()
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS billing_invoices_worm_delete
                ON {_schema_prefix()}billing_invoices
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER billing_invoices_worm_delete
                BEFORE DELETE ON {_schema_prefix()}billing_invoices
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}billing_invoices_worm_guard()
                """
            )
        )

    if table_exists(bind, "billing_payments", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}billing_payments_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.status IS DISTINCT FROM OLD.status THEN
                        IF NEW.invoice_id IS DISTINCT FROM OLD.invoice_id
                            OR NEW.provider IS DISTINCT FROM OLD.provider
                            OR NEW.provider_payment_id IS DISTINCT FROM OLD.provider_payment_id
                            OR NEW.currency IS DISTINCT FROM OLD.currency
                            OR NEW.amount IS DISTINCT FROM OLD.amount
                            OR NEW.captured_at IS DISTINCT FROM OLD.captured_at
                            OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
                            OR NEW.ledger_tx_id IS DISTINCT FROM OLD.ledger_tx_id
                            OR NEW.external_statement_line_id IS DISTINCT FROM OLD.external_statement_line_id
                            OR NEW.audit_event_id IS DISTINCT FROM OLD.audit_event_id
                            OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                            RAISE EXCEPTION 'billing_payments is WORM';
                        END IF;
                        RETURN NEW;
                    END IF;
                    RAISE EXCEPTION 'billing_payments is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS billing_payments_worm_update
                ON {_schema_prefix()}billing_payments
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER billing_payments_worm_update
                BEFORE UPDATE ON {_schema_prefix()}billing_payments
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}billing_payments_worm_guard()
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS billing_payments_worm_delete
                ON {_schema_prefix()}billing_payments
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER billing_payments_worm_delete
                BEFORE DELETE ON {_schema_prefix()}billing_payments
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}billing_payments_worm_guard()
                """
            )
        )

    if table_exists(bind, "billing_refunds", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}billing_refunds_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.status IS DISTINCT FROM OLD.status THEN
                        IF NEW.payment_id IS DISTINCT FROM OLD.payment_id
                            OR NEW.provider_refund_id IS DISTINCT FROM OLD.provider_refund_id
                            OR NEW.currency IS DISTINCT FROM OLD.currency
                            OR NEW.amount IS DISTINCT FROM OLD.amount
                            OR NEW.refunded_at IS DISTINCT FROM OLD.refunded_at
                            OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
                            OR NEW.ledger_tx_id IS DISTINCT FROM OLD.ledger_tx_id
                            OR NEW.external_statement_line_id IS DISTINCT FROM OLD.external_statement_line_id
                            OR NEW.audit_event_id IS DISTINCT FROM OLD.audit_event_id
                            OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                            RAISE EXCEPTION 'billing_refunds is WORM';
                        END IF;
                        RETURN NEW;
                    END IF;
                    RAISE EXCEPTION 'billing_refunds is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS billing_refunds_worm_update
                ON {_schema_prefix()}billing_refunds
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER billing_refunds_worm_update
                BEFORE UPDATE ON {_schema_prefix()}billing_refunds
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}billing_refunds_worm_guard()
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS billing_refunds_worm_delete
                ON {_schema_prefix()}billing_refunds
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER billing_refunds_worm_delete
                BEFORE DELETE ON {_schema_prefix()}billing_refunds
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}billing_refunds_worm_guard()
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if is_postgres(bind):
        for table_name in ("billing_invoices", "billing_payments", "billing_refunds"):
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
                    DROP TRIGGER IF EXISTS {table_name}_worm_delete
                    ON {_schema_prefix()}{table_name}
                    """
                )
            )
            op.execute(
                sa.text(
                    f"""
                    DROP FUNCTION IF EXISTS {_schema_prefix()}{table_name}_worm_guard()
                    """
                )
            )

    op.drop_table("reconciliation_links", schema=SCHEMA)
    op.drop_table("billing_refunds", schema=SCHEMA)
    op.drop_table("billing_payments", schema=SCHEMA)
    op.drop_table("billing_invoices", schema=SCHEMA)

    if is_postgres(bind):
        op.execute(sa.text("DROP TYPE IF EXISTS reconciliation_link_status"))
        op.execute(sa.text("DROP TYPE IF EXISTS reconciliation_link_direction"))
        op.execute(sa.text("DROP TYPE IF EXISTS billing_refund_status"))
        op.execute(sa.text("DROP TYPE IF EXISTS billing_payment_status"))
        op.execute(sa.text("DROP TYPE IF EXISTS billing_invoice_status"))
