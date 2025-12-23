"""Billing v0: clearing batch and invoice fields

Revision ID: 20250210_0043_billing_invoice_clearing_batch_fields
Revises: 20280201_0042_invoice_state_machine_v15
Create Date: 2025-02-10 00:43:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    SCHEMA,
    column_exists,
    constraint_exists,
    create_index_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    is_postgres,
)


# revision identifiers, used by Alembic.
revision = "20250210_0043_billing_invoice_clearing_batch_fields"
down_revision = "20280201_0042_invoice_state_machine_v15"
branch_labels = None
depends_on = None

CLEARING_BATCH_STATES = ["OPEN", "CLOSED"]

clearing_batch_state_t = postgresql.ENUM(name="clearing_batch_state", schema=SCHEMA, create_type=False)


def upgrade():
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    ensure_pg_enum(bind, "clearing_batch_state", CLEARING_BATCH_STATES, schema=SCHEMA)
    for value in CLEARING_BATCH_STATES:
        ensure_pg_enum_value(bind, "clearing_batch_state", value, schema=SCHEMA)

    if not column_exists(bind, "clearing_batch", "tenant_id", schema=SCHEMA):
        op.add_column("clearing_batch", sa.Column("tenant_id", sa.Integer(), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "clearing_batch", "total_qty", schema=SCHEMA):
        op.add_column("clearing_batch", sa.Column("total_qty", sa.Numeric(18, 3), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "clearing_batch", "state", schema=SCHEMA):
        op.add_column(
            "clearing_batch",
            sa.Column("state", clearing_batch_state_t, nullable=False, server_default="OPEN"),
            schema=SCHEMA,
        )
    if not column_exists(bind, "clearing_batch", "closed_at", schema=SCHEMA):
        op.add_column("clearing_batch", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)

    create_index_if_not_exists(
        bind,
        "ix_clearing_batch_tenant_period",
        "clearing_batch",
        ["tenant_id", "date_from", "date_to"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_clearing_batch_tenant_id", "clearing_batch", ["tenant_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_clearing_batch_state", "clearing_batch", ["state"], schema=SCHEMA)

    if not constraint_exists(bind, "clearing_batch", "uq_clearing_batch_tenant_period", schema=SCHEMA):
        op.execute(
            f"ALTER TABLE {SCHEMA}.clearing_batch "
            "ADD CONSTRAINT uq_clearing_batch_tenant_period UNIQUE (tenant_id, date_from, date_to)"
        )

    if not column_exists(bind, "invoices", "clearing_batch_id", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("clearing_batch_id", sa.String(length=36), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "invoices", "number", schema=SCHEMA):
        op.add_column("invoices", sa.Column("number", sa.String(length=64), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "invoices", "pdf_object_key", schema=SCHEMA):
        op.add_column("invoices", sa.Column("pdf_object_key", sa.String(length=512), nullable=True), schema=SCHEMA)

    create_index_if_not_exists(bind, "ix_invoices_number", "invoices", ["number"], schema=SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_invoices_clearing_batch_id",
        "invoices",
        ["clearing_batch_id"],
        schema=SCHEMA,
    )

    if not constraint_exists(bind, "invoices", "uq_invoice_number", schema=SCHEMA):
        op.execute(
            f"ALTER TABLE {SCHEMA}.invoices "
            "ADD CONSTRAINT uq_invoice_number UNIQUE (number)"
        )

    if not constraint_exists(bind, "invoices", "uq_invoice_clearing_batch", schema=SCHEMA):
        op.execute(
            f"ALTER TABLE {SCHEMA}.invoices "
            "ADD CONSTRAINT uq_invoice_clearing_batch UNIQUE (clearing_batch_id)"
        )


def downgrade():
    pass
