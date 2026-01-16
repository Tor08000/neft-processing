"""Export jobs for async reports.

Revision ID: 20299060_0136_export_jobs
Revises: 20299050_0135_support_ticket_sla
Create Date: 2026-02-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.types import GUID


revision = "20299060_0136_export_jobs"
down_revision = "20299050_0135_support_ticket_sla"
branch_labels = None
depends_on = None


REPORT_TYPES = ["cards", "users", "transactions", "documents", "audit", "support"]
FORMATS = ["CSV"]
STATUSES = ["QUEUED", "RUNNING", "DONE", "FAILED", "CANCELED", "EXPIRED"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "export_job_report_type", REPORT_TYPES, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "export_job_format", FORMATS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "export_job_status", STATUSES, schema=DB_SCHEMA)

    report_type_enum = safe_enum(bind, "export_job_report_type", REPORT_TYPES, schema=DB_SCHEMA)
    format_enum = safe_enum(bind, "export_job_format", FORMATS, schema=DB_SCHEMA)
    status_enum = safe_enum(bind, "export_job_status", STATUSES, schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "export_jobs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=False),
        sa.Column("report_type", report_type_enum, nullable=False),
        sa.Column("format", format_enum, nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="QUEUED"),
        sa.Column("file_object_key", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_export_jobs_org_created_at",
        "export_jobs",
        ["org_id", "created_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_export_jobs_status",
        "export_jobs",
        ["status"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("export_jobs", schema=DB_SCHEMA)
