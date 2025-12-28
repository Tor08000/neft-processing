"""Add ERP acknowledgement fields to accounting export batches.

Revision ID: 20290510_0046_accounting_export_erp_ack
Revises: 20290501_0045_document_status_lifecycle
Create Date: 2029-05-10 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.helpers import column_exists
from app.db.schema import resolve_db_schema

revision = "20290510_0046_accounting_export_erp_ack"
down_revision = "20290501_0045_document_status_lifecycle"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    bind = op.get_bind()
    if not column_exists(bind, "accounting_export_batches", "erp_system", schema=SCHEMA):
        op.add_column(
            "accounting_export_batches",
            sa.Column("erp_system", sa.String(length=32), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "accounting_export_batches", "erp_import_id", schema=SCHEMA):
        op.add_column(
            "accounting_export_batches",
            sa.Column("erp_import_id", sa.String(length=128), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "accounting_export_batches", "erp_status", schema=SCHEMA):
        op.add_column(
            "accounting_export_batches",
            sa.Column("erp_status", sa.String(length=16), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "accounting_export_batches", "erp_message", schema=SCHEMA):
        op.add_column(
            "accounting_export_batches",
            sa.Column("erp_message", sa.Text(), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "accounting_export_batches", "erp_processed_at", schema=SCHEMA):
        op.add_column(
            "accounting_export_batches",
            sa.Column("erp_processed_at", sa.DateTime(timezone=True), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
