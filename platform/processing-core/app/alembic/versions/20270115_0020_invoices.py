"""invoice tables

Revision ID: 20270115_0020
Revises: 20270101_0019_external_request_logs
Create Date: 2027-01-15 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
    table_exists,
)
from app.models.invoice import InvoiceStatus

# revision identifiers, used by Alembic.
revision = "20270115_0020"
down_revision = "20270101_0019_external_request_logs"
branch_labels = None
depends_on = None

INVOICE_STATUS_VALUES = [status.value for status in InvoiceStatus]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "invoicestatus", values=INVOICE_STATUS_VALUES)
    invoice_status_enum = safe_enum(bind, "invoicestatus", INVOICE_STATUS_VALUES)

    create_table_if_not_exists(
        bind,
        "invoices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_with_tax", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            invoice_status_enum,
            nullable=False,
            server_default=InvoiceStatus.DRAFT.value,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_number", sa.String(length=64), nullable=True),
    )

    create_table_if_not_exists(
        bind,
        "invoice_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "invoice_id", sa.String(length=36), sa.ForeignKey("invoices.id"), nullable=False
        ),
        sa.Column("operation_id", sa.String(length=128), nullable=True),
        sa.Column("card_id", sa.String(length=64), nullable=True),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("liters", sa.Numeric(18, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 3), nullable=True),
        sa.Column("line_amount", sa.BigInteger(), nullable=False),
        sa.Column("tax_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("partner_id", sa.String(length=64), nullable=True),
        sa.Column("azs_id", sa.String(length=64), nullable=True),
    )

    create_index_if_not_exists(bind, "ix_invoices_client_id", "invoices", ["client_id"])
    create_index_if_not_exists(bind, "ix_invoices_status", "invoices", ["status"])
    create_index_if_not_exists(bind, "ix_invoices_period_from", "invoices", ["period_from"])
    create_index_if_not_exists(bind, "ix_invoices_period_to", "invoices", ["period_to"])
    create_index_if_not_exists(
        bind, "ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"]
    )


def downgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "invoice_lines"):
        drop_index_if_exists(bind, "ix_invoice_lines_invoice_id")
        drop_table_if_exists(bind, "invoice_lines")
    if table_exists(bind, "invoices"):
        drop_index_if_exists(bind, "ix_invoices_period_to")
        drop_index_if_exists(bind, "ix_invoices_period_from")
        drop_index_if_exists(bind, "ix_invoices_status")
        drop_index_if_exists(bind, "ix_invoices_client_id")
        drop_table_if_exists(bind, "invoices")
    if bind.dialect.name == "postgresql":
        bind.exec_driver_sql("DROP TYPE IF EXISTS public.invoicestatus")
