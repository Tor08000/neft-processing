"""Add XLSX to export job formats.

Revision ID: 20299070_0137_export_job_format_xlsx
Revises: 20299060_0136_export_jobs
Create Date: 2026-02-16 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from alembic_helpers import DB_SCHEMA, ensure_pg_enum_value, is_postgres

revision = "20299070_0137_export_job_format_xlsx"
down_revision = "20299060_0136_export_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if is_postgres(bind):
        ensure_pg_enum_value(bind, "export_job_format", "XLSX", schema=DB_SCHEMA)


def downgrade() -> None:
    # Enum values are left in place to avoid data loss.
    return None
