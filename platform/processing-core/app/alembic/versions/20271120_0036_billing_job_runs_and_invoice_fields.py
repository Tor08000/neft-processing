"""Billing v1.3: job runs, task links, invoice pdf fields

Revision ID: 20271120_0036_billing_job_runs_and_invoice_fields
Revises: 20271101_0035_billing_period_type_adhoc
Create Date: 2024-11-20 00:36:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    SCHEMA,
    column_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    create_index_if_not_exists,
    is_postgres,
)
from app.db.types import GUID

# revision identifiers, used by Alembic.
revision = "20271120_0036_billing_job_runs_and_invoice_fields"
down_revision = "20271101_0035_billing_period_type_adhoc"
branch_labels = None
depends_on = None

BILLING_JOB_TYPES = [
    "BILLING_DAILY",
    "BILLING_FINALIZE",
    "INVOICE_MONTHLY",
    "RECONCILIATION",
    "MANUAL_RUN",
    "PDF_GENERATE",
]
BILLING_JOB_STATUSES = ["STARTED", "SUCCESS", "FAILED"]
INVOICE_PDF_STATUS = ["NONE", "QUEUED", "GENERATING", "READY", "FAILED"]
TASK_TYPES = ["MONTHLY_RUN", "PDF_GENERATE", "INVOICE_SEND"]
TASK_STATUSES = ["QUEUED", "RUNNING", "SUCCESS", "FAILED"]

billing_job_type_t = postgresql.ENUM(name="billing_job_type", schema=SCHEMA, create_type=False)
billing_job_status_t = postgresql.ENUM(name="billing_job_status", schema=SCHEMA, create_type=False)
invoice_pdf_status_t = postgresql.ENUM(name="invoice_pdf_status", schema=SCHEMA, create_type=False)
billing_task_type_t = postgresql.ENUM(name="billing_task_type", schema=SCHEMA, create_type=False)
billing_task_status_t = postgresql.ENUM(name="billing_task_status", schema=SCHEMA, create_type=False)


def upgrade():
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    ensure_pg_enum(bind, "billing_job_type", BILLING_JOB_TYPES, schema=SCHEMA)
    for value in BILLING_JOB_TYPES:
        ensure_pg_enum_value(bind, "billing_job_type", value, schema=SCHEMA)

    ensure_pg_enum(bind, "billing_job_status", BILLING_JOB_STATUSES, schema=SCHEMA)
    for value in BILLING_JOB_STATUSES:
        ensure_pg_enum_value(bind, "billing_job_status", value, schema=SCHEMA)

    ensure_pg_enum(bind, "invoice_pdf_status", INVOICE_PDF_STATUS, schema=SCHEMA)
    for value in INVOICE_PDF_STATUS:
        ensure_pg_enum_value(bind, "invoice_pdf_status", value, schema=SCHEMA)

    ensure_pg_enum(bind, "billing_task_type", TASK_TYPES, schema=SCHEMA)
    for value in TASK_TYPES:
        ensure_pg_enum_value(bind, "billing_task_type", value, schema=SCHEMA)

    ensure_pg_enum(bind, "billing_task_status", TASK_STATUSES, schema=SCHEMA)
    for value in TASK_STATUSES:
        ensure_pg_enum_value(bind, "billing_task_status", value, schema=SCHEMA)

    job_run_columns = [
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("job_type", billing_job_type_t, nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("status", billing_job_status_t, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("invoice_id", sa.String(length=36), nullable=True),
        sa.Column("billing_period_id", GUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_ref", sa.JSON(), nullable=True),
    ]
    job_run_indexes = [
        ("ix_billing_job_runs_type_status", ["job_type", "status"]),
        ("ix_billing_job_runs_type_status_started", ["job_type", "status", "started_at"]),
        ("ix_billing_job_runs_started_at", ["started_at"]),
        ("ix_billing_job_runs_finished_at", ["finished_at"]),
        ("ix_billing_job_runs_celery_task_id", ["celery_task_id"]),
        ("ix_billing_job_runs_invoice_id", ["invoice_id"]),
        ("ix_billing_job_runs_billing_period_id", ["billing_period_id"]),
    ]
    create_table_if_not_exists(
        bind,
        "billing_job_runs",
        schema=SCHEMA,
        columns=job_run_columns,
        indexes=job_run_indexes,
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

    if not column_exists(bind, "invoices", "pdf_status", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column(
                "pdf_status",
                invoice_pdf_status_t,
                nullable=False,
                server_default="NONE",
            ),
            schema=SCHEMA,
        )
    if not column_exists(bind, "invoices", "pdf_url", schema=SCHEMA):
        op.add_column("invoices", sa.Column("pdf_url", sa.String(length=512), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "invoices", "pdf_hash", schema=SCHEMA):
        op.add_column("invoices", sa.Column("pdf_hash", sa.String(length=64), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "invoices", "pdf_version", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("pdf_version", sa.Integer(), nullable=False, server_default="1"),
            schema=SCHEMA,
        )
    if not column_exists(bind, "invoices", "pdf_generated_at", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "invoices", "pdf_error", schema=SCHEMA):
        op.add_column("invoices", sa.Column("pdf_error", sa.Text(), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "invoices", "sent_at", schema=SCHEMA):
        op.add_column("invoices", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)

    create_index_if_not_exists(bind, "ix_invoices_pdf_status", "invoices", ["pdf_status"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_invoices_sent_at", "invoices", ["sent_at"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "billing_task_links",
        schema=SCHEMA,
        columns=[
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("task_id", sa.String(length=128), nullable=False, unique=True),
            sa.Column("task_name", sa.String(length=128), nullable=False),
            sa.Column("task_type", billing_task_type_t, nullable=False),
            sa.Column("job_run_id", GUID(), sa.ForeignKey(f"{SCHEMA}.billing_job_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("invoice_id", sa.String(length=36), nullable=True),
            sa.Column("billing_period_id", GUID(), nullable=True),
            sa.Column("status", billing_task_status_t, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
        ],
        indexes=[
            ("ix_billing_task_links_task_id", ["task_id"]),
            ("ix_billing_task_links_invoice_id", ["invoice_id"]),
            ("ix_billing_task_links_billing_period_id", ["billing_period_id"]),
            ("ix_billing_task_links_job_run_id", ["job_run_id"]),
        ],
    )

    if not column_exists(bind, "billing_task_links", "error", schema=SCHEMA):
        op.add_column("billing_task_links", sa.Column("error", sa.Text(), nullable=True), schema=SCHEMA)


def downgrade():
    pass
