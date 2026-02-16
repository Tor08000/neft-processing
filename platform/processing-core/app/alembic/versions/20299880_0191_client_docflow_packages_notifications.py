"""Client docflow packages and notifications.

Revision ID: 20299880_0191_client_docflow_packages_notifications
Revises: 20299870_0190_client_doc_signing
Create Date: 2026-02-16 01:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import DB_SCHEMA
from db.types import GUID

revision = "20299880_0191_client_docflow_packages_notifications"
down_revision = "20299870_0190_client_doc_signing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_client_audit_events_client_created", "client_audit_events", ["client_id", "created_at"], schema=DB_SCHEMA)
    op.create_index("ix_client_audit_events_app_created", "client_audit_events", ["application_id", "created_at"], schema=DB_SCHEMA)
    op.create_index("ix_client_audit_events_doc_created", "client_audit_events", ["doc_id", "created_at"], schema=DB_SCHEMA)

    op.create_table(
        "client_document_packages",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("application_id", GUID(), nullable=True),
        sa.Column("package_kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    op.create_index("ix_client_document_packages_client_created", "client_document_packages", ["client_id", "created_at"], schema=DB_SCHEMA)

    op.create_table(
        "client_document_package_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("package_id", GUID(), sa.ForeignKey(f"{DB_SCHEMA}.client_document_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_id", GUID(), sa.ForeignKey(f"{DB_SCHEMA}.client_generated_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    op.create_index("ix_client_document_package_items_package_id", "client_document_package_items", ["package_id"], schema=DB_SCHEMA)

    op.create_table(
        "client_docflow_notifications",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("meta_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema=DB_SCHEMA,
    )
    op.create_index("ix_client_docflow_notifications_client_created", "client_docflow_notifications", ["client_id", "created_at"], schema=DB_SCHEMA)
    op.create_index("ix_client_docflow_notifications_client_read", "client_docflow_notifications", ["client_id", "read_at"], schema=DB_SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_client_docflow_notifications_client_read", table_name="client_docflow_notifications", schema=DB_SCHEMA)
    op.drop_index("ix_client_docflow_notifications_client_created", table_name="client_docflow_notifications", schema=DB_SCHEMA)
    op.drop_table("client_docflow_notifications", schema=DB_SCHEMA)

    op.drop_index("ix_client_document_package_items_package_id", table_name="client_document_package_items", schema=DB_SCHEMA)
    op.drop_table("client_document_package_items", schema=DB_SCHEMA)

    op.drop_index("ix_client_document_packages_client_created", table_name="client_document_packages", schema=DB_SCHEMA)
    op.drop_table("client_document_packages", schema=DB_SCHEMA)

    op.drop_index("ix_client_audit_events_doc_created", table_name="client_audit_events", schema=DB_SCHEMA)
    op.drop_index("ix_client_audit_events_app_created", table_name="client_audit_events", schema=DB_SCHEMA)
    op.drop_index("ix_client_audit_events_client_created", table_name="client_audit_events", schema=DB_SCHEMA)
