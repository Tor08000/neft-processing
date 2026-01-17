"""Add timezone to client employees.

Revision ID: 20299110_0141_client_employee_timezone
Revises: 20299100_0140_export_job_progress
Create Date: 2026-02-20 00:00:01.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA


revision = "20299110_0141_client_employee_timezone"
down_revision = "20299100_0140_export_job_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_employees",
        sa.Column("timezone", sa.String(64), nullable=True),
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("client_employees", "timezone", schema=DB_SCHEMA)
