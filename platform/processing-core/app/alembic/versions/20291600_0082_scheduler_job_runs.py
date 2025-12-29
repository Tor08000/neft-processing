"""Add scheduler job evidence tables.

Revision ID: 20291600_0082_scheduler_job_runs
Revises: 20291590_0081_fleet_control_v3
Create Date: 2029-06-00 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import create_index_if_not_exists, create_table_if_not_exists, table_exists
from app.db.schema import resolve_db_schema


SCHEMA = resolve_db_schema().schema

revision = "20291600_0082_scheduler_job_runs"
down_revision = "20291590_0081_fleet_control_v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "scheduler_job_runs", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "scheduler_job_runs",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(36), primary_key=True),
                sa.Column("job_name", sa.String(255), nullable=False),
                sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("status", sa.String(32), nullable=False),
                sa.Column("error", sa.Text, nullable=True),
                sa.Column("celery_task_id", sa.String(255), nullable=True),
            ),
        )
        create_index_if_not_exists(
            bind, "ix_scheduler_job_runs_job_name", "scheduler_job_runs", ["job_name"], schema=SCHEMA
        )
        create_index_if_not_exists(
            bind,
            "ix_scheduler_job_runs_finished_at",
            "scheduler_job_runs",
            ["finished_at"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "scheduler_state", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "scheduler_state",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(64), primary_key=True),
                sa.Column(
                    "schedule_task_count",
                    sa.Integer,
                    nullable=False,
                    server_default="0",
                ),
                sa.Column("schedule_loaded_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            ),
        )


def downgrade() -> None:
    op.drop_table("scheduler_state", schema=SCHEMA)
    op.drop_table("scheduler_job_runs", schema=SCHEMA)
