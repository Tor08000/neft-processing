"""Report schedules for client exports.

Revision ID: 20299070_0137_report_schedules
Revises: 20299060_0136_export_jobs
Create Date: 2026-02-05 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.types import GUID


revision = "20299070_0137_report_schedules"
down_revision = "20299060_0136_export_jobs"
branch_labels = None
depends_on = None


REPORT_TYPES = ["cards", "users", "transactions", "documents", "audit", "support"]
FORMATS = ["CSV"]
REPORT_SCHEDULE_KIND = ["DAILY", "WEEKLY", "MONTHLY"]
REPORT_SCHEDULE_STATUS = ["ACTIVE", "PAUSED", "DISABLED"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "report_schedule_kind", REPORT_SCHEDULE_KIND, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "report_schedule_status", REPORT_SCHEDULE_STATUS, schema=DB_SCHEMA)
    schedule_kind_enum = safe_enum(bind, "report_schedule_kind", REPORT_SCHEDULE_KIND, schema=DB_SCHEMA)
    schedule_status_enum = safe_enum(bind, "report_schedule_status", REPORT_SCHEDULE_STATUS, schema=DB_SCHEMA)
    report_type_enum = safe_enum(bind, "export_job_report_type", REPORT_TYPES, schema=DB_SCHEMA)
    export_format_enum = safe_enum(bind, "export_job_format", FORMATS, schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "report_schedules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("created_by_user_id", sa.String(128), nullable=False),
        sa.Column("report_type", report_type_enum, nullable=False),
        sa.Column("format", export_format_enum, nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("schedule_kind", schedule_kind_enum, nullable=False),
        sa.Column("schedule_meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("delivery_in_app", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("delivery_email_to_creator", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("delivery_email_to_roles", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", schedule_status_enum, nullable=False, server_default="ACTIVE"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_report_schedules_org_id", "report_schedules", ["org_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_report_schedules_status", "report_schedules", ["status"], schema=DB_SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_report_schedules_org_status",
        "report_schedules",
        ["org_id", "status"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_report_schedules_next_run_at", "report_schedules", ["next_run_at"], schema=DB_SCHEMA
    )
    create_index_if_not_exists(
        bind,
        "ix_report_schedules_creator",
        "report_schedules",
        ["created_by_user_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("report_schedules", schema=DB_SCHEMA)
