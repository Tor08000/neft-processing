"""Billing v1.3 follow-up hardening

Revision ID: 20271205_0037_billing_pdf_and_tasks
Revises: 20271120_0036_billing_job_runs_and_invoice_fields
Create Date: 2024-12-05 00:37:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import (
    SCHEMA,
    column_exists,
    create_index_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    index_exists,
    is_postgres,
)

# revision identifiers, used by Alembic.
revision = "20271205_0037_billing_pdf_and_tasks"
down_revision = "20271120_0036_billing_job_runs_and_invoice_fields"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    ensure_pg_enum(bind, "billing_task_type", ["MONTHLY_RUN", "PDF_GENERATE", "INVOICE_SEND"], schema=SCHEMA)
    ensure_pg_enum(bind, "billing_task_status", ["QUEUED", "RUNNING", "SUCCESS", "FAILED"], schema=SCHEMA)
    ensure_pg_enum_value(bind, "billing_job_type", "PDF_GENERATE", schema=SCHEMA)
    ensure_pg_enum_value(bind, "invoice_pdf_status", "READY", schema=SCHEMA)

    if column_exists(bind, "invoices", "pdf_hash", schema=SCHEMA):
        op.alter_column("invoices", "pdf_hash", type_=sa.String(length=64), schema=SCHEMA)
    if column_exists(bind, "invoices", "pdf_version", schema=SCHEMA):
        bind.exec_driver_sql(f"UPDATE {SCHEMA}.invoices SET pdf_version = 1 WHERE pdf_version IS NULL")
        op.alter_column(
            "invoices",
            "pdf_version",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="1",
            schema=SCHEMA,
        )
    if column_exists(bind, "invoices", "pdf_status", schema=SCHEMA) and not index_exists(
        bind, "ix_invoices_pdf_status", schema=SCHEMA
    ):
        op.create_index("ix_invoices_pdf_status", "invoices", ["pdf_status"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_billing_job_runs_celery_task_id", "billing_job_runs", ["celery_task_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_billing_job_runs_invoice_id", "billing_job_runs", ["invoice_id"], schema=SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_billing_job_runs_billing_period_id",
        "billing_job_runs",
        ["billing_period_id"],
        schema=SCHEMA,
    )
    billing_task_type_t = postgresql.ENUM(name="billing_task_type", schema=SCHEMA, create_type=False)
    if not column_exists(bind, "billing_task_links", "task_type", schema=SCHEMA):
        op.add_column(
            "billing_task_links",
            sa.Column("task_type", billing_task_type_t, nullable=False, server_default="PDF_GENERATE"),
            schema=SCHEMA,
        )
    if not index_exists(bind, "ix_billing_task_links_task_id", schema=SCHEMA):
        create_index_if_not_exists(bind, "ix_billing_task_links_task_id", "billing_task_links", ["task_id"], schema=SCHEMA)


def downgrade():
    pass
