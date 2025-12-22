"""Finance v1.4: invoice lifecycle extensions

Revision ID: 20271220_0038_finance_invoice_extensions
Revises: 20271205_0037_billing_pdf_and_tasks
Create Date: 2024-12-20 00:38:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import (
    SCHEMA,
    column_exists,
    create_index_if_not_exists,
    ensure_pg_enum_value,
    is_postgres,
)
from app.db.types import GUID

# revision identifiers, used by Alembic.
revision = "20271220_0038_finance_invoice_extensions"
down_revision = "20271205_0037_billing_pdf_and_tasks"
branch_labels = None
depends_on = None

INVOICE_STATUS_VALUES = ["DELIVERED", "PARTIALLY_PAID", "VOIDED"]
BILLING_JOB_TYPE_VALUES = ["INVOICE_SEND", "CREDIT_NOTE_PDF", "FINANCE_EXPORT", "BALANCE_REBUILD"]


def upgrade():
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    for value in INVOICE_STATUS_VALUES:
        ensure_pg_enum_value(bind, "invoicestatus", value, schema=SCHEMA)

    for value in BILLING_JOB_TYPE_VALUES:
        ensure_pg_enum_value(bind, "billing_job_type", value, schema=SCHEMA)

    if not column_exists(bind, "invoices", "due_date", schema=SCHEMA):
        op.add_column("invoices", sa.Column("due_date", sa.Date(), nullable=True), schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_invoices_due_date", "invoices", ["due_date"], schema=SCHEMA)

    if not column_exists(bind, "invoices", "payment_terms_days", schema=SCHEMA):
        op.add_column("invoices", sa.Column("payment_terms_days", sa.Integer(), nullable=True), schema=SCHEMA)

    if not column_exists(bind, "invoices", "amount_paid", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("amount_paid", sa.BigInteger(), nullable=False, server_default="0"),
            schema=SCHEMA,
        )
        bind.exec_driver_sql(
            f"UPDATE {SCHEMA}.invoices "
            "SET amount_paid = COALESCE(total_with_tax, 0) WHERE status = 'PAID' OR paid_at IS NOT NULL"
        )

    if not column_exists(bind, "invoices", "amount_due", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("amount_due", sa.BigInteger(), nullable=False, server_default="0"),
            schema=SCHEMA,
        )
        bind.exec_driver_sql(
            f"UPDATE {SCHEMA}.invoices SET amount_due = COALESCE(total_with_tax, 0) - COALESCE(amount_paid, 0)"
        )

    if not column_exists(bind, "invoices", "delivered_at", schema=SCHEMA):
        op.add_column("invoices", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)

    if not column_exists(bind, "invoices", "external_delivery_id", schema=SCHEMA):
        op.add_column("invoices", sa.Column("external_delivery_id", sa.String(length=128), nullable=True), schema=SCHEMA)

    if not column_exists(bind, "invoices", "external_delivery_provider", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("external_delivery_provider", sa.String(length=64), nullable=True),
            schema=SCHEMA,
        )

    if not column_exists(bind, "invoices", "payment_reference", schema=SCHEMA):
        op.add_column("invoices", sa.Column("payment_reference", sa.String(length=128), nullable=True), schema=SCHEMA)

    if not column_exists(bind, "invoices", "accounting_exported_at", schema=SCHEMA):
        op.add_column("invoices", sa.Column("accounting_exported_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)

    if not column_exists(bind, "invoices", "accounting_export_batch_id", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("accounting_export_batch_id", GUID(), nullable=True),
            schema=SCHEMA,
        )


def downgrade():
    pass
