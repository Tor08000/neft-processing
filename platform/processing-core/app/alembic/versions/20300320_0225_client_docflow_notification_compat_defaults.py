"""Client docflow notification compatibility defaults.

Revision ID: 20300320_0225_client_docflow_notification_compat_defaults
Revises: 20300310_0224_billing_invoice_pdf_artifact_repair
Create Date: 2026-04-21 20:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists


revision = "20300320_0225_client_docflow_notification_compat_defaults"
down_revision = "20300310_0224_billing_invoice_pdf_artifact_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    table = "client_docflow_notifications"
    qualified = f"{DB_SCHEMA}.{table}"

    if column_exists(bind, table, "channel", schema=DB_SCHEMA):
        op.execute(f"UPDATE {qualified} SET channel = 'in_app' WHERE channel IS NULL")
        op.alter_column(table, "channel", server_default=sa.text("'in_app'"), nullable=False, schema=DB_SCHEMA)
    if column_exists(bind, table, "body", schema=DB_SCHEMA):
        op.execute(f"UPDATE {qualified} SET body = coalesce(body, message, title, '')")
        op.alter_column(table, "body", server_default=sa.text("''"), nullable=False, schema=DB_SCHEMA)
    if column_exists(bind, table, "event_type", schema=DB_SCHEMA):
        op.execute(f"UPDATE {qualified} SET event_type = coalesce(event_type, kind, 'INFO')")
        op.alter_column(table, "event_type", server_default=sa.text("'INFO'"), nullable=False, schema=DB_SCHEMA)
    if column_exists(bind, table, "meta_json", schema=DB_SCHEMA):
        op.execute(f"UPDATE {qualified} SET meta_json = coalesce(meta_json, payload::jsonb, '{{}}'::jsonb)")
        op.alter_column(table, "meta_json", server_default=sa.text("'{}'::jsonb"), nullable=False, schema=DB_SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    table = "client_docflow_notifications"

    if column_exists(bind, table, "channel", schema=DB_SCHEMA):
        op.alter_column(table, "channel", server_default=None, nullable=False, schema=DB_SCHEMA)
    if column_exists(bind, table, "body", schema=DB_SCHEMA):
        op.alter_column(table, "body", server_default=None, nullable=False, schema=DB_SCHEMA)
    if column_exists(bind, table, "event_type", schema=DB_SCHEMA):
        op.alter_column(table, "event_type", server_default=None, nullable=False, schema=DB_SCHEMA)
    if column_exists(bind, table, "meta_json", schema=DB_SCHEMA):
        op.alter_column(table, "meta_json", server_default=sa.text("'{}'::jsonb"), nullable=False, schema=DB_SCHEMA)
