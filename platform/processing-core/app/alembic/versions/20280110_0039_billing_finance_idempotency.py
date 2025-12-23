"""Billing v1.4.1 finance/idempotency extensions

Revision ID: 20280110_0039_billing_finance_idempotency
Revises: 20271220_0038_finance_invoice_extensions
Create Date: 2028-01-10 00:39:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    SCHEMA,
    column_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    index_exists,
    is_postgres,
)
from app.db.types import GUID

# revision identifiers, used by Alembic.
revision = "20280110_0039_billing_finance_idempotency"
down_revision = "20271220_0038_finance_invoice_extensions"
branch_labels = None
depends_on = None

NEW_JOB_TYPES = ["CLEARING_RUN", "FINANCE_PAYMENT", "FINANCE_CREDIT_NOTE", "BILLING_SEED"]
PAYMENT_STATUSES = ["POSTED", "FAILED"]
CREDIT_STATUSES = ["POSTED", "FAILED"]


def upgrade():
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    for value in NEW_JOB_TYPES:
        ensure_pg_enum_value(bind, "billing_job_type", value, schema=SCHEMA)

    ensure_pg_enum(bind, "invoice_payment_status", PAYMENT_STATUSES, schema=SCHEMA)
    ensure_pg_enum(bind, "credit_note_status", CREDIT_STATUSES, schema=SCHEMA)
    for value in PAYMENT_STATUSES:
        ensure_pg_enum_value(bind, "invoice_payment_status", value, schema=SCHEMA)
    for value in CREDIT_STATUSES:
        ensure_pg_enum_value(bind, "credit_note_status", value, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "invoice_payments",
        schema=SCHEMA,
        columns=[
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("invoice_id", sa.String(length=36), nullable=False, index=True),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True, index=True),
            sa.Column(
                "status",
                postgresql.ENUM(name="invoice_payment_status", schema=SCHEMA, create_type=False),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
    )

    create_table_if_not_exists(
        bind,
        "credit_notes",
        schema=SCHEMA,
        columns=[
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("invoice_id", sa.String(length=36), nullable=False, index=True),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column("reason", sa.String(length=255), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True, index=True),
            sa.Column(
                "status",
                postgresql.ENUM(name="credit_note_status", schema=SCHEMA, create_type=False),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
    )

    if not index_exists(bind, "ix_invoice_payments_invoice_id", schema=SCHEMA):
        op.create_index(
            "ix_invoice_payments_invoice_id",
            "invoice_payments",
            ["invoice_id"],
            schema=SCHEMA,
        )

    if not index_exists(bind, "ix_credit_notes_invoice_id", schema=SCHEMA):
        op.create_index(
            "ix_credit_notes_invoice_id",
            "credit_notes",
            ["invoice_id"],
            schema=SCHEMA,
        )


def downgrade():
    # Keep the upgrade idempotent; do not drop enums or tables to avoid data loss
    pass
