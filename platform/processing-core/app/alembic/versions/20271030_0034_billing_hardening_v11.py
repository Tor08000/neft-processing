"""billing hardening v1.1

Revision ID: 20271030_0034_billing_hardening_v11
Revises: 20271020_0033_billing_periods
Create Date: 2027-10-30 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

from app.db.types import GUID
from app.db.schema import resolve_db_schema
from app.alembic.utils import ensure_pg_enum, ensure_pg_enum_value, column_exists, constraint_exists, index_exists, table_exists
from app.models.financial_adjustment import FinancialAdjustmentKind, RelatedEntityType
from app.models.billing_reconciliation import (
    BillingReconciliationStatus,
    BillingReconciliationVerdict,
)

# revision identifiers, used by Alembic.
revision = "20271030_0034_billing_hardening_v11"
down_revision = "20271020_0033_billing_periods"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


recon_status_enum = sa.Enum(
    BillingReconciliationStatus,
    name="billing_reconciliation_status",
    schema=SCHEMA,
    create_type=False,
)
recon_verdict_enum = sa.Enum(
    BillingReconciliationVerdict,
    name="billing_reconciliation_verdict",
    schema=SCHEMA,
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # Extend enums
    if bind.dialect.name == "postgresql":
        for value in (FinancialAdjustmentKind.CREDIT.value, FinancialAdjustmentKind.DEBIT.value):
            ensure_pg_enum_value(bind, "financial_adjustment_kind", value, schema=SCHEMA)
        ensure_pg_enum_value(bind, "financial_adjustment_related", RelatedEntityType.BILLING_PERIOD.value, schema=SCHEMA)
        ensure_pg_enum(
            bind,
            "billing_reconciliation_status",
            values=[item.value for item in BillingReconciliationStatus],
            schema=SCHEMA,
        )
        ensure_pg_enum(
            bind,
            "billing_reconciliation_verdict",
            values=[item.value for item in BillingReconciliationVerdict],
            schema=SCHEMA,
        )

    # invoices billing_period_id
    if not column_exists(bind, "invoices", "billing_period_id", schema=SCHEMA):
        op.add_column(
            "invoices",
            sa.Column("billing_period_id", GUID(), sa.ForeignKey("billing_periods.id"), nullable=True),
            schema=SCHEMA,
        )
    if not index_exists(bind, "ix_invoices_billing_period_id", schema=SCHEMA):
        op.create_index("ix_invoices_billing_period_id", "invoices", ["billing_period_id"], schema=SCHEMA)

    # backfill billing_period_id based on dates
    bind.execute(
        text(
            f"""
            UPDATE {SCHEMA}.invoices inv
            SET billing_period_id = bp.id
            FROM {SCHEMA}.billing_periods bp
            WHERE inv.billing_period_id IS NULL
              AND bp.start_at::date = inv.period_from
              AND bp.end_at::date = inv.period_to
            """
        )
    )

    # try to enforce not null when safe
    null_count = bind.execute(
        text(f"SELECT COUNT(1) FROM {SCHEMA}.invoices WHERE billing_period_id IS NULL")
    ).scalar()
    if null_count == 0:
        op.alter_column("invoices", "billing_period_id", nullable=False, schema=SCHEMA)

    if not constraint_exists(bind, "invoices", "uq_invoice_scope", schema=SCHEMA):
        op.create_unique_constraint(
            "uq_invoice_scope",
            "invoices",
            ["client_id", "billing_period_id", "currency"],
            schema=SCHEMA,
        )

    # invoice_lines uniqueness
    if not index_exists(bind, "ix_invoice_lines_operation_per_invoice_nonnull", schema=SCHEMA):
        op.create_index(
            "ix_invoice_lines_operation_per_invoice_nonnull",
            "invoice_lines",
            ["invoice_id", "operation_id"],
            unique=True,
            schema=SCHEMA,
            postgresql_where=sa.text("operation_id IS NOT NULL"),
            sqlite_where=sa.text("operation_id IS NOT NULL"),
        )

    # billing_summary total_amount widen
    op.alter_column(
        "billing_summary",
        "total_amount",
        type_=sa.BigInteger(),
        postgresql_using="total_amount::bigint",
        schema=SCHEMA,
    )

    # reconciliation tables
    if not table_exists(bind, "billing_reconciliation_runs", schema=SCHEMA):
        op.create_table(
            "billing_reconciliation_runs",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("billing_period_id", GUID(), sa.ForeignKey("billing_periods.id"), nullable=False),
            sa.Column(
                "status",
                recon_status_enum,
                nullable=False,
                server_default=BillingReconciliationStatus.OK.value,
            ),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_invoices", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ok_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("mismatch_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("missing_ledger_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            schema=SCHEMA,
        )
    if not index_exists(bind, "ix_billing_reconciliation_runs_period", schema=SCHEMA):
        op.create_index(
            "ix_billing_reconciliation_runs_period",
            "billing_reconciliation_runs",
            ["billing_period_id"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "billing_reconciliation_items", schema=SCHEMA):
        op.create_table(
            "billing_reconciliation_items",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column(
                "run_id",
                GUID(),
                sa.ForeignKey("billing_reconciliation_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("invoice_id", sa.String(length=36), nullable=False),
            sa.Column("client_id", sa.String(length=64), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column(
                "verdict",
                recon_verdict_enum,
                nullable=False,
                server_default=BillingReconciliationVerdict.OK.value,
            ),
            sa.Column("diff_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            schema=SCHEMA,
        )
    if not index_exists(bind, "ix_billing_reconciliation_items_run", schema=SCHEMA):
        op.create_index("ix_billing_reconciliation_items_run", "billing_reconciliation_items", ["run_id"], schema=SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_billing_reconciliation_items_run", table_name="billing_reconciliation_items", schema=SCHEMA)
    op.drop_table("billing_reconciliation_items", schema=SCHEMA)
    op.drop_index("ix_billing_reconciliation_runs_period", table_name="billing_reconciliation_runs", schema=SCHEMA)
    op.drop_table("billing_reconciliation_runs", schema=SCHEMA)

    if index_exists(bind, "ix_invoice_lines_operation_per_invoice_nonnull", schema=SCHEMA):
        op.drop_index("ix_invoice_lines_operation_per_invoice_nonnull", table_name="invoice_lines", schema=SCHEMA)
    op.alter_column("invoice_lines", "operation_id", nullable=True, schema=SCHEMA)

    if constraint_exists(bind, "invoices", "uq_invoice_scope", schema=SCHEMA):
        op.drop_constraint("uq_invoice_scope", "invoices", schema=SCHEMA)
    op.alter_column("invoices", "billing_period_id", nullable=True, schema=SCHEMA)
    if column_exists(bind, "invoices", "billing_period_id", schema=SCHEMA):
        op.drop_index("ix_invoices_billing_period_id", table_name="invoices", schema=SCHEMA)
        op.drop_column("invoices", "billing_period_id", schema=SCHEMA)

    op.alter_column(
        "billing_summary",
        "total_amount",
        type_=sa.Integer(),
        schema=SCHEMA,
    )

    if bind.dialect.name == "postgresql":
        # enum values remain for safety
        pass
