"""Client onboarding documents.

Revision ID: 20299840_0187_client_documents
Revises: 20299830_0186_client_onboarding_applications
Create Date: 2026-02-16 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA
from db.types import GUID

revision = "20299840_0187_client_documents"
down_revision = "20299830_0186_client_onboarding_applications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_documents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_application_id", GUID(), sa.ForeignKey(f"{DB_SCHEMA}.client_onboarding_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_type", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'UPLOADED'")),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    op.create_index("ix_client_documents_application_id", "client_documents", ["client_application_id"], schema=DB_SCHEMA)
    op.create_index("ix_client_documents_doc_type", "client_documents", ["doc_type"], schema=DB_SCHEMA)
    op.create_index("ix_client_documents_status", "client_documents", ["status"], schema=DB_SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_client_documents_status", table_name="client_documents", schema=DB_SCHEMA)
    op.drop_index("ix_client_documents_doc_type", table_name="client_documents", schema=DB_SCHEMA)
    op.drop_index("ix_client_documents_application_id", table_name="client_documents", schema=DB_SCHEMA)
    op.drop_table("client_documents", schema=DB_SCHEMA)
