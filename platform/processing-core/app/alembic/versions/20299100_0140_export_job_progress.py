"""Add export job progress fields.

Revision ID: 20299100_0140_export_job_progress
Revises: 20299090_0139_user_notification_preferences
Create Date: 2026-02-15 00:00:02.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import column_exists, resolve_db_schema


revision = "20299100_0140_export_job_progress"
down_revision = "20299090_0139_user_notification_preferences"
branch_labels = None
depends_on = None


SCHEMA_RESOLUTION = resolve_db_schema()
SCHEMA = SCHEMA_RESOLUTION.schema


def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists(bind, "export_jobs", "processed_rows", schema=SCHEMA):
        op.add_column(
            "export_jobs",
            sa.Column("processed_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
            schema=SCHEMA,
        )
    if not column_exists(bind, "export_jobs", "estimated_total_rows", schema=SCHEMA):
        op.add_column(
            "export_jobs",
            sa.Column("estimated_total_rows", sa.Integer(), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "export_jobs", "progress_percent", schema=SCHEMA):
        op.add_column(
            "export_jobs",
            sa.Column("progress_percent", sa.Integer(), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if column_exists(bind, "export_jobs", "progress_percent", schema=SCHEMA):
        op.drop_column("export_jobs", "progress_percent", schema=SCHEMA)
    if column_exists(bind, "export_jobs", "estimated_total_rows", schema=SCHEMA):
        op.drop_column("export_jobs", "estimated_total_rows", schema=SCHEMA)
    if column_exists(bind, "export_jobs", "processed_rows", schema=SCHEMA):
        op.drop_column("export_jobs", "processed_rows", schema=SCHEMA)
