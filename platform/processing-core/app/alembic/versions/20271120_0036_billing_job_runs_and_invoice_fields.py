"""Add billing_job_runs table and invoice fields

Revision ID: 20271120_0036_billing_job_runs_and_invoice_fields
Revises: 20271101_0035_billing_period_type_adhoc
Create Date: 2024-11-20 00:36:00.000000
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
revision = "20271120_0036_billing_job_runs_and_invoice_fields"
down_revision = "20271101_0035_billing_period_type_adhoc"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    ensure_pg_enum(
        bind,
        "billing_job_type",
        ["BILLING_DAILY", "BILLING_FINALIZE", "INVOICE_MONTHLY", "RECONCILIATION", "MANUAL_RUN"],
        schema=SCHEMA,
    )
    ensure_pg_enum(bind, "billing_job_status", ["STARTED", "SUCCESS", "FAILED"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "billing_job_runs",
        schema=SCHEMA,
        columns=[
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("job_type", sa.Enum(name="billing_job_type", schema=SCHEMA), nullable=False),
            sa.Column("params", sa.JSON(), nullable=True),
            sa.Column("status", sa.Enum(name="billing_job_status", schema=SCHEMA), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("metrics", sa.JSON(), nullable=True),
        ],
        indexes=[
            ("ix_billing_job_runs_type_status", ["job_type", "status"]),
        ],
    )

    if not column_exists(bind, "invoices", "pdf_url", schema=SCHEMA):
        op.add_column("invoices", sa.Column("pdf_url", sa.String(length=512), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "invoices", "sent_at", schema=SCHEMA):
        op.add_column("invoices", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)

    if not index_exists(bind, "ix_invoices_sent_at", schema=SCHEMA):
        op.create_index("ix_invoices_sent_at", "invoices", ["sent_at"], schema=SCHEMA)


def downgrade():
    bind = op.get_bind()

    if index_exists(bind, "ix_invoices_sent_at", schema=SCHEMA):
        op.drop_index("ix_invoices_sent_at", table_name="invoices", schema=SCHEMA)
    if column_exists(bind, "invoices", "sent_at", schema=SCHEMA):
        op.drop_column("invoices", "sent_at", schema=SCHEMA)
    if column_exists(bind, "invoices", "pdf_url", schema=SCHEMA):
        op.drop_column("invoices", "pdf_url", schema=SCHEMA)

    drop_table_if_exists(bind, "billing_job_runs", schema=SCHEMA)

    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.billing_job_type CASCADE")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.billing_job_status CASCADE")
