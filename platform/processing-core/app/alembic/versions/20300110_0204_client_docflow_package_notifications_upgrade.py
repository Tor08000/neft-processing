"""Upgrade client docflow packages + notifications schema.

Revision ID: 20300110_0204_client_docflow_package_notifications_upgrade
Revises: 20299880_0191_client_docflow_packages_notifications
Create Date: 2026-02-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA

revision = "20300110_0204_client_docflow_package_notifications_upgrade"
down_revision = "20299880_0191_client_docflow_packages_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_document_packages", sa.Column("sha256", sa.Text(), nullable=True), schema=DB_SCHEMA)
    op.add_column("client_document_packages", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)
    op.add_column("client_document_packages", sa.Column("error_code", sa.Text(), nullable=True), schema=DB_SCHEMA)

    op.create_unique_constraint(
        "uq_client_document_package_items_package_doc",
        "client_document_package_items",
        ["package_id", "doc_id"],
        schema=DB_SCHEMA,
    )

    op.add_column("client_docflow_notifications", sa.Column("kind", sa.Text(), nullable=True), schema=DB_SCHEMA)
    op.add_column("client_docflow_notifications", sa.Column("message", sa.Text(), nullable=True), schema=DB_SCHEMA)
    op.add_column("client_docflow_notifications", sa.Column("payload", sa.JSON(), nullable=True), schema=DB_SCHEMA)
    op.add_column("client_docflow_notifications", sa.Column("severity", sa.Text(), nullable=False, server_default="INFO"), schema=DB_SCHEMA)
    op.add_column("client_docflow_notifications", sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")), schema=DB_SCHEMA)
    op.add_column("client_docflow_notifications", sa.Column("dedupe_key", sa.Text(), nullable=True), schema=DB_SCHEMA)

    op.execute(f"UPDATE {DB_SCHEMA}.client_docflow_notifications SET kind = coalesce(event_type, 'DOC_STATUS_CHANGED')")
    op.execute(f"UPDATE {DB_SCHEMA}.client_docflow_notifications SET message = coalesce(body, title)")
    op.execute(f"UPDATE {DB_SCHEMA}.client_docflow_notifications SET payload = coalesce(meta_json, '{{}}'::json)")
    op.execute(f"UPDATE {DB_SCHEMA}.client_docflow_notifications SET is_read = (read_at is not null)")

    op.alter_column("client_docflow_notifications", "kind", nullable=False, schema=DB_SCHEMA)
    op.alter_column("client_docflow_notifications", "message", nullable=False, schema=DB_SCHEMA)
    op.alter_column("client_docflow_notifications", "payload", nullable=False, schema=DB_SCHEMA)

    op.create_index(
        "ix_client_docflow_notifications_user_created",
        "client_docflow_notifications",
        ["user_id", "created_at"],
        schema=DB_SCHEMA,
    )
    op.create_index(
        "ix_client_docflow_notifications_dedupe_key",
        "client_docflow_notifications",
        ["dedupe_key"],
        unique=True,
        schema=DB_SCHEMA,
        postgresql_where=sa.text("dedupe_key is not null"),
    )


def downgrade() -> None:
    op.drop_index("ix_client_docflow_notifications_dedupe_key", table_name="client_docflow_notifications", schema=DB_SCHEMA)
    op.drop_index("ix_client_docflow_notifications_user_created", table_name="client_docflow_notifications", schema=DB_SCHEMA)
    op.drop_column("client_docflow_notifications", "dedupe_key", schema=DB_SCHEMA)
    op.drop_column("client_docflow_notifications", "is_read", schema=DB_SCHEMA)
    op.drop_column("client_docflow_notifications", "severity", schema=DB_SCHEMA)
    op.drop_column("client_docflow_notifications", "payload", schema=DB_SCHEMA)
    op.drop_column("client_docflow_notifications", "message", schema=DB_SCHEMA)
    op.drop_column("client_docflow_notifications", "kind", schema=DB_SCHEMA)

    op.drop_constraint("uq_client_document_package_items_package_doc", "client_document_package_items", schema=DB_SCHEMA)
    op.drop_column("client_document_packages", "error_code", schema=DB_SCHEMA)
    op.drop_column("client_document_packages", "expires_at", schema=DB_SCHEMA)
    op.drop_column("client_document_packages", "sha256", schema=DB_SCHEMA)
