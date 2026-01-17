"""Add export job ETA tracking fields.

Revision ID: 20299140_0144_export_job_eta_fields
Revises: 20299130_0143_helpdesk_inbound_webhooks
Create Date: 2026-02-18 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import column_exists, resolve_db_schema


revision = "20299140_0144_export_job_eta_fields"
down_revision = "20299130_0143_helpdesk_inbound_webhooks"
branch_labels = None
depends_on = None


SCHEMA_RESOLUTION = resolve_db_schema()
SCHEMA = SCHEMA_RESOLUTION.schema


def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists(bind, "export_jobs", "progress_updated_at", schema=SCHEMA):
        op.add_column(
            "export_jobs",
            sa.Column("progress_updated_at", sa.DateTime(timezone=True), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "export_jobs", "avg_rows_per_sec", schema=SCHEMA):
        op.add_column(
            "export_jobs",
            sa.Column("avg_rows_per_sec", sa.Float(), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "export_jobs", "last_heartbeat_at", schema=SCHEMA):
        op.add_column(
            "export_jobs",
            sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if column_exists(bind, "export_jobs", "last_heartbeat_at", schema=SCHEMA):
        op.drop_column("export_jobs", "last_heartbeat_at", schema=SCHEMA)
    if column_exists(bind, "export_jobs", "avg_rows_per_sec", schema=SCHEMA):
        op.drop_column("export_jobs", "avg_rows_per_sec", schema=SCHEMA)
    if column_exists(bind, "export_jobs", "progress_updated_at", schema=SCHEMA):
        op.drop_column("export_jobs", "progress_updated_at", schema=SCHEMA)
