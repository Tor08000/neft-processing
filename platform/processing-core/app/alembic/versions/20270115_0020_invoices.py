"""invoice tables

Revision ID: 20270115_0020
Revises: 20270101_0019_external_request_logs
Create Date: 2027-01-15 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.models.invoice import InvoiceStatus

# revision identifiers, used by Alembic.
revision = "20270115_0020"
down_revision = "20270101_0019_external_request_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("client_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("period_from", sa.Date(), nullable=False, index=True),
        sa.Column("period_to", sa.Date(), nullable=False, index=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_with_tax", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum(InvoiceStatus, name="invoicestatus"),
            nullable=False,
            index=True,
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

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("invoice_id", sa.String(length=36), sa.ForeignKey("invoices.id"), nullable=False, index=True),
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

    op.create_index("ix_invoices_client_id", "invoices", ["client_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_period_from", "invoices", ["period_from"])
    op.create_index("ix_invoices_period_to", "invoices", ["period_to"])
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_index("ix_invoices_period_to", table_name="invoices")
    op.drop_index("ix_invoices_period_from", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_client_id", table_name="invoices")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    sa.Enum(name="invoicestatus").drop(op.get_bind(), checkfirst=False)
