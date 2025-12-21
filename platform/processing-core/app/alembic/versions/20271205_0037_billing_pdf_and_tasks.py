"""Billing v1.3 PDF fields and task links

Revision ID: 20271205_0037_billing_pdf_and_tasks
Revises: 20271120_0036_billing_job_runs_and_invoice_fields
Create Date: 2024-12-05 00:37:00.000000
"""

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import (
    SCHEMA,
    column_exists,
    create_table_if_not_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    index_exists,
)
from app.db.types import GUID

# revision identifiers, used by Alembic.
revision = "20271205_0037_billing_pdf_and_tasks"
down_revision = "20271120_0036_billing_job_runs_and_invoice_fields"
branch_labels = None
depends_on = None


INVOICE_PDF_STATUS = ["NONE", "QUEUED", "GENERATING", "READY", "FAILED"]
TASK_TYPES = ["MONTHLY_RUN", "PDF_GENERATE", "INVOICE_SEND"]
TASK_STATUSES = ["QUEUED", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"]


def upgrade():
    bind = op.get_bind()

    ensure_pg_enum(bind, "invoice_pdf_status", INVOICE_PDF_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "billing_task_type", TASK_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "billing_task_status", TASK_STATUSES, schema=SCHEMA)

    if not column_exists(bind, "invoices", "pdf_status", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column(
                "pdf_status",
                sa.Enum(name="invoice_pdf_status", schema=SCHEMA),
                nullable=False,
                server_default="NONE",
            ),
            schema=SCHEMA,
        )
    if not column_exists(bind, "invoices", "pdf_generated_at", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "invoices", "pdf_hash", schema=SCHEMA):
        op.add_column("invoices", sa.Column("pdf_hash", sa.String(length=256), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "invoices", "pdf_version", schema=SCHEMA):
        op.add_column("invoices", sa.Column("pdf_version", sa.Integer(), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "invoices", "pdf_error", schema=SCHEMA):
        op.add_column("invoices", sa.Column("pdf_error", sa.Text(), nullable=True), schema=SCHEMA)

    if not column_exists(bind, "billing_job_runs", "celery_task_id", schema=SCHEMA):
        op.add_column(
            "billing_job_runs",
            sa.Column("celery_task_id", sa.Text(), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "billing_job_runs", "correlation_id", schema=SCHEMA):
        op.add_column(
            "billing_job_runs",
            sa.Column("correlation_id", sa.Text(), nullable=True),
            schema=SCHEMA,
        )
    if not index_exists(bind, "ix_billing_job_runs_correlation_id", schema=SCHEMA):
        op.create_index(
            "ix_billing_job_runs_correlation_id",
            "billing_job_runs",
            ["correlation_id"],
            schema=SCHEMA,
        )
    if not column_exists(bind, "billing_job_runs", "updated_at", schema=SCHEMA):
        op.add_column(
            "billing_job_runs",
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "billing_job_runs", "attempts", schema=SCHEMA):
        op.add_column("billing_job_runs", sa.Column("attempts", sa.Integer(), nullable=True, server_default="0"), schema=SCHEMA)
    if not column_exists(bind, "billing_job_runs", "last_heartbeat_at", schema=SCHEMA):
        op.add_column(
            "billing_job_runs",
            sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "billing_job_runs", "result_ref", schema=SCHEMA):
        op.add_column("billing_job_runs", sa.Column("result_ref", sa.JSON(), nullable=True), schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "billing_task_links",
        schema=SCHEMA,
        columns=[
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("invoice_id", sa.String(length=36), nullable=False, index=True),
            sa.Column("task_type", sa.Enum(name="billing_task_type", schema=SCHEMA), nullable=False),
            sa.Column("task_id", sa.Text(), nullable=False),
            sa.Column("status", sa.Enum(name="billing_task_status", schema=SCHEMA), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
        ],
        indexes=[("ix_billing_task_links_invoice_id_type", ["invoice_id", "task_type"])],
    )


def downgrade():
    bind = op.get_bind()

    drop_table_if_exists(bind, "billing_task_links", schema=SCHEMA)

    for column in ["result_ref", "last_heartbeat_at", "attempts", "updated_at", "correlation_id", "celery_task_id"]:
        if column_exists(bind, "billing_job_runs", column, schema=SCHEMA):
            op.drop_column("billing_job_runs", column, schema=SCHEMA)
    if index_exists(bind, "ix_billing_job_runs_correlation_id", schema=SCHEMA):
        op.drop_index("ix_billing_job_runs_correlation_id", table_name="billing_job_runs", schema=SCHEMA)

    for column in ["pdf_error", "pdf_version", "pdf_hash", "pdf_generated_at", "pdf_status"]:
        if column_exists(bind, "invoices", column, schema=SCHEMA):
            op.drop_column("invoices", column, schema=SCHEMA)

    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.billing_task_status CASCADE")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.billing_task_type CASCADE")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.invoice_pdf_status CASCADE")
