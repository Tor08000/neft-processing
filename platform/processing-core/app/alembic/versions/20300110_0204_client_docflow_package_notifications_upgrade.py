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


def column_exists(schema: str, table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = :table_name
                  AND column_name = :column_name
            )
            """
        ),
        {"schema": schema, "table_name": table_name, "column_name": column_name},
    )
    return bool(result.scalar())


def constraint_exists(schema: str, table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_schema = :schema
                  AND table_name = :table_name
                  AND constraint_name = :constraint_name
            )
            """
        ),
        {"schema": schema, "table_name": table_name, "constraint_name": constraint_name},
    )
    return bool(result.scalar())


def index_exists(schema: str, table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = :schema
                  AND tablename = :table_name
                  AND indexname = :index_name
            )
            """
        ),
        {"schema": schema, "table_name": table_name, "index_name": index_name},
    )
    return bool(result.scalar())


def get_column_data_type(schema: str, table_name: str, column_name: str) -> str | None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table_name
              AND column_name = :column_name
            """
        ),
        {"schema": schema, "table_name": table_name, "column_name": column_name},
    )
    return result.scalar()


def upgrade() -> None:
    if not column_exists(DB_SCHEMA, "client_document_packages", "sha256"):
        op.add_column("client_document_packages", sa.Column("sha256", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(DB_SCHEMA, "client_document_packages", "expires_at"):
        op.add_column("client_document_packages", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)
    if not column_exists(DB_SCHEMA, "client_document_packages", "error_code"):
        op.add_column("client_document_packages", sa.Column("error_code", sa.Text(), nullable=True), schema=DB_SCHEMA)

    if not constraint_exists(DB_SCHEMA, "client_document_package_items", "uq_client_document_package_items_package_doc"):
        op.create_unique_constraint(
            "uq_client_document_package_items_package_doc",
            "client_document_package_items",
            ["package_id", "doc_id"],
            schema=DB_SCHEMA,
        )

    if not column_exists(DB_SCHEMA, "client_docflow_notifications", "kind"):
        op.add_column("client_docflow_notifications", sa.Column("kind", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(DB_SCHEMA, "client_docflow_notifications", "message"):
        op.add_column("client_docflow_notifications", sa.Column("message", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(DB_SCHEMA, "client_docflow_notifications", "payload"):
        op.add_column("client_docflow_notifications", sa.Column("payload", sa.JSON(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(DB_SCHEMA, "client_docflow_notifications", "severity"):
        op.add_column("client_docflow_notifications", sa.Column("severity", sa.Text(), nullable=False, server_default="INFO"), schema=DB_SCHEMA)
    if not column_exists(DB_SCHEMA, "client_docflow_notifications", "is_read"):
        op.add_column("client_docflow_notifications", sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")), schema=DB_SCHEMA)
    if not column_exists(DB_SCHEMA, "client_docflow_notifications", "dedupe_key"):
        op.add_column("client_docflow_notifications", sa.Column("dedupe_key", sa.Text(), nullable=True), schema=DB_SCHEMA)

    op.execute(f"UPDATE {DB_SCHEMA}.client_docflow_notifications SET kind = coalesce(event_type, 'DOC_STATUS_CHANGED')")
    op.execute(f"UPDATE {DB_SCHEMA}.client_docflow_notifications SET message = coalesce(body, title)")
    payload_exists = column_exists(DB_SCHEMA, "client_docflow_notifications", "payload")
    meta_json_exists = column_exists(DB_SCHEMA, "client_docflow_notifications", "meta_json")
    payload_data_type = get_column_data_type(DB_SCHEMA, "client_docflow_notifications", "payload") if payload_exists else None

    if payload_exists and payload_data_type == "json":
        if meta_json_exists:
            op.execute(
                f"UPDATE {DB_SCHEMA}.client_docflow_notifications "
                "SET payload = coalesce(meta_json::json, '{}'::json)"
            )
        else:
            op.execute(f"UPDATE {DB_SCHEMA}.client_docflow_notifications SET payload = coalesce(payload, '{{}}'::json)")
    elif payload_exists:
        if meta_json_exists:
            op.execute(
                f"UPDATE {DB_SCHEMA}.client_docflow_notifications "
                "SET payload = coalesce(meta_json::jsonb, '{}'::jsonb)"
            )
        else:
            op.execute(f"UPDATE {DB_SCHEMA}.client_docflow_notifications SET payload = coalesce(payload, '{{}}'::jsonb)")
    op.execute(f"UPDATE {DB_SCHEMA}.client_docflow_notifications SET is_read = (read_at is not null)")

    op.alter_column("client_docflow_notifications", "kind", nullable=False, schema=DB_SCHEMA)
    op.alter_column("client_docflow_notifications", "message", nullable=False, schema=DB_SCHEMA)
    op.alter_column("client_docflow_notifications", "payload", nullable=False, schema=DB_SCHEMA)

    if not index_exists(DB_SCHEMA, "client_docflow_notifications", "ix_client_docflow_notifications_user_created"):
        op.create_index(
            "ix_client_docflow_notifications_user_created",
            "client_docflow_notifications",
            ["user_id", "created_at"],
            schema=DB_SCHEMA,
        )
    if not index_exists(DB_SCHEMA, "client_docflow_notifications", "ix_client_docflow_notifications_dedupe_key"):
        op.create_index(
            "ix_client_docflow_notifications_dedupe_key",
            "client_docflow_notifications",
            ["dedupe_key"],
            unique=True,
            schema=DB_SCHEMA,
            postgresql_where=sa.text("dedupe_key is not null"),
        )


def downgrade() -> None:
    if index_exists(DB_SCHEMA, "client_docflow_notifications", "ix_client_docflow_notifications_dedupe_key"):
        op.drop_index("ix_client_docflow_notifications_dedupe_key", table_name="client_docflow_notifications", schema=DB_SCHEMA)
    if index_exists(DB_SCHEMA, "client_docflow_notifications", "ix_client_docflow_notifications_user_created"):
        op.drop_index("ix_client_docflow_notifications_user_created", table_name="client_docflow_notifications", schema=DB_SCHEMA)
    if column_exists(DB_SCHEMA, "client_docflow_notifications", "dedupe_key"):
        op.drop_column("client_docflow_notifications", "dedupe_key", schema=DB_SCHEMA)
    if column_exists(DB_SCHEMA, "client_docflow_notifications", "is_read"):
        op.drop_column("client_docflow_notifications", "is_read", schema=DB_SCHEMA)
    if column_exists(DB_SCHEMA, "client_docflow_notifications", "severity"):
        op.drop_column("client_docflow_notifications", "severity", schema=DB_SCHEMA)
    if column_exists(DB_SCHEMA, "client_docflow_notifications", "payload"):
        op.drop_column("client_docflow_notifications", "payload", schema=DB_SCHEMA)
    if column_exists(DB_SCHEMA, "client_docflow_notifications", "message"):
        op.drop_column("client_docflow_notifications", "message", schema=DB_SCHEMA)
    if column_exists(DB_SCHEMA, "client_docflow_notifications", "kind"):
        op.drop_column("client_docflow_notifications", "kind", schema=DB_SCHEMA)

    if constraint_exists(DB_SCHEMA, "client_document_package_items", "uq_client_document_package_items_package_doc"):
        op.drop_constraint("uq_client_document_package_items_package_doc", "client_document_package_items", schema=DB_SCHEMA)
    if column_exists(DB_SCHEMA, "client_document_packages", "error_code"):
        op.drop_column("client_document_packages", "error_code", schema=DB_SCHEMA)
    if column_exists(DB_SCHEMA, "client_document_packages", "expires_at"):
        op.drop_column("client_document_packages", "expires_at", schema=DB_SCHEMA)
    if column_exists(DB_SCHEMA, "client_document_packages", "sha256"):
        op.drop_column("client_document_packages", "sha256", schema=DB_SCHEMA)
