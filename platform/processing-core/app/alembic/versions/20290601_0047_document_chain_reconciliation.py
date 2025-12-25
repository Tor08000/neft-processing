"""Add document hash and reconciliation request link.

Revision ID: 20290601_0047_document_chain_reconciliation
Revises: 20290520_0046_risk_scores
Create Date: 2029-06-01 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.db.types import GUID
from app.db.schema import resolve_db_schema


revision = "20290601_0047_document_chain_reconciliation"
down_revision = "20290520_0046_risk_scores"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("document_hash", sa.String(length=64), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "invoices",
        sa.Column("reconciliation_request_id", GUID(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_invoices_reconciliation_request_id",
        "invoices",
        ["reconciliation_request_id"],
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_invoices_reconciliation_request_id",
        "invoices",
        "reconciliation_requests",
        ["reconciliation_request_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
