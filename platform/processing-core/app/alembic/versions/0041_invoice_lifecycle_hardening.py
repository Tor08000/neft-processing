"""Invoice lifecycle hardening

Revision ID: 0041_invoice_lifecycle_hardening
Revises: 0040_merge_heads
Create Date: 2028-01-21 00:41:00.000000
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

# revision identifiers, used by Alembic.
revision = "0041_invoice_lifecycle_hardening"
down_revision = "0040_merge_heads"
branch_labels = None
depends_on = None

NEW_INVOICE_STATUSES = ["REFUNDED", "CLOSED"]
TIMESTAMP_COLUMNS = ("cancelled_at", "closed_at", "refunded_at")
TIMESTAMP_INDEXES = (
    ("ix_invoices_paid_at", ["paid_at"]),
    ("ix_invoices_sent_at", ["sent_at"]),
    ("ix_invoices_delivered_at", ["delivered_at"]),
    ("ix_invoices_accounting_exported_at", ["accounting_exported_at"]),
    ("ix_invoices_client_status", ["client_id", "status"]),
)


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    for status in NEW_INVOICE_STATUSES:
        ensure_pg_enum_value(bind, "invoicestatus", status, schema=SCHEMA)

    for column in TIMESTAMP_COLUMNS:
        if not column_exists(bind, "invoices", column, schema=SCHEMA):
            op.add_column(
                "invoices",
                sa.Column(column, sa.DateTime(timezone=True), nullable=True),
                schema=SCHEMA,
            )

    for name, columns in TIMESTAMP_INDEXES:
        create_index_if_not_exists(bind, name, "invoices", columns, schema=SCHEMA)


def downgrade() -> None:
    # Downgrade intentionally left empty to keep migration idempotent and avoid data loss.
    pass
