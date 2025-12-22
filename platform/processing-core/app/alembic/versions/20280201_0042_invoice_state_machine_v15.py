"""Invoice state machine v1.5 hardening

Revision ID: 20280201_0042
Revises: 20280121_0041
Create Date: 2028-02-01 00:42:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.utils import (
    SCHEMA,
    column_exists,
    create_table_if_not_exists,
    ensure_pg_enum_value,
    is_postgres,
)
from app.db.types import GUID

# revision identifiers, used by Alembic.
revision = "20280201_0042_invoice_state_machine_v15"
down_revision = "20280121_0041_invoice_lifecycle_hardening"
branch_labels = None
depends_on = None

NEW_INVOICE_STATUSES = ("OVERDUE", "CREDITED")


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    for status in NEW_INVOICE_STATUSES:
        ensure_pg_enum_value(bind, "invoicestatus", status, schema=SCHEMA)

    if not column_exists(bind, "invoices", "credited_amount", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("credited_amount", sa.BigInteger(), nullable=False, server_default="0"),
            schema=SCHEMA,
        )
    if not column_exists(bind, "invoices", "credited_at", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
            schema=SCHEMA,
        )

    create_table_if_not_exists(
        bind,
        "invoice_transition_logs",
        schema=SCHEMA,
        columns=[
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("invoice_id", sa.String(length=36), nullable=False, index=True),
            sa.Column("from_status", sa.Enum(name="invoicestatus", schema=SCHEMA), nullable=False),
            sa.Column("to_status", sa.Enum(name="invoicestatus", schema=SCHEMA), nullable=False),
            sa.Column("actor", sa.String(length=64), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
        indexes=[("ix_invoice_transition_logs_invoice_id", ["invoice_id"])],
    )


def downgrade() -> None:
    # Idempotent migration; no downgrade to avoid data loss.
    pass
