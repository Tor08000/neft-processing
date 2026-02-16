"""Client generated onboarding documents.

Revision ID: 20299860_0189_client_generated_documents
Revises: 20299850_0188_onboarding_review_client_link
Create Date: 2026-02-16 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA
from db.types import GUID

revision = "20299860_0189_client_generated_documents"
down_revision = "20299850_0188_onboarding_review_client_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_generated_documents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_application_id", GUID(), sa.ForeignKey(f"{DB_SCHEMA}.client_onboarding_applications.id", ondelete="CASCADE"), nullable=True),
        sa.Column("client_id", GUID(), sa.ForeignKey(f"{DB_SCHEMA}.clients.id"), nullable=True),
        sa.Column("doc_kind", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=False, server_default=sa.text("'application/pdf'")),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("template_id", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("(client_application_id IS NOT NULL) OR (client_id IS NOT NULL)", name="ck_client_generated_docs_owner_set"),
        sa.UniqueConstraint("client_application_id", "doc_kind", "version", name="uq_client_generated_docs_app_kind_version"),
        sa.UniqueConstraint("client_id", "doc_kind", "version", name="uq_client_generated_docs_client_kind_version"),
        schema=DB_SCHEMA,
    )
    op.create_index(
        "ix_client_generated_documents_application_id",
        "client_generated_documents",
        ["client_application_id"],
        schema=DB_SCHEMA,
    )
    op.create_index("ix_client_generated_documents_client_id", "client_generated_documents", ["client_id"], schema=DB_SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_client_generated_documents_client_id", table_name="client_generated_documents", schema=DB_SCHEMA)
    op.drop_index("ix_client_generated_documents_application_id", table_name="client_generated_documents", schema=DB_SCHEMA)
    op.drop_table("client_generated_documents", schema=DB_SCHEMA)
