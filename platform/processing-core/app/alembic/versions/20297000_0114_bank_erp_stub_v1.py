"""Bank + ERP stub providers.

Revision ID: 20297000_0114_bank_erp_stub_v1
Revises: 20295100_0113_vehicle_maintenance_v1, 20296000_0113_service_bookings_v1, 20296000_0113_service_completion_proofs_v1
Create Date: 2026-04-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from app.alembic.helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from app.db.types import GUID


revision = "20297000_0114_bank_erp_stub_v1"
down_revision = (
    "20295100_0113_vehicle_maintenance_v1",
    "20296000_0113_service_bookings_v1",
    "20296000_0113_service_completion_proofs_v1",
)
branch_labels = None
depends_on = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


BANK_STUB_PAYMENT_STATUS = ["CREATED", "POSTED", "SETTLED", "REVERSED"]
ERP_STUB_EXPORT_STATUS = ["CREATED", "SENT", "ACKED", "FAILED"]
ERP_STUB_EXPORT_TYPE = ["INVOICES", "PAYMENTS", "SETTLEMENT", "RECONCILIATION"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "bank_stub_payment_status", BANK_STUB_PAYMENT_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "erp_stub_export_status", ERP_STUB_EXPORT_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "erp_stub_export_type", ERP_STUB_EXPORT_TYPE, schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "bank_stub_payments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", GUID(), nullable=False),
        sa.Column("payment_ref", sa.String(length=128), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column(
            "status",
            safe_enum(bind, "bank_stub_payment_status", BANK_STUB_PAYMENT_STATUS, schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("payment_ref", name="uq_bank_stub_payments_ref"),
        sa.UniqueConstraint("idempotency_key", name="uq_bank_stub_payments_idempotency"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_stub_payments_invoice",
        "bank_stub_payments",
        ["invoice_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "bank_stub_statements",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("period_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", JSON_TYPE, nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "checksum", name="uq_bank_stub_statements_checksum"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_stub_statements_period",
        "bank_stub_statements",
        ["tenant_id", "period_to"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "bank_stub_statement_lines",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("statement_id", GUID(), nullable=False),
        sa.Column("payment_ref", sa.String(length=128), nullable=False),
        sa.Column("invoice_number", sa.String(length=64), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["statement_id"], [f"{DB_SCHEMA}.bank_stub_statements.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("statement_id", "payment_ref", name="uq_bank_stub_statement_lines_ref"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_bank_stub_statement_lines_statement",
        "bank_stub_statement_lines",
        ["statement_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "erp_stub_exports",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("export_ref", sa.String(length=128), nullable=False),
        sa.Column(
            "export_type",
            safe_enum(bind, "erp_stub_export_type", ERP_STUB_EXPORT_TYPE, schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            safe_enum(bind, "erp_stub_export_status", ERP_STUB_EXPORT_STATUS, schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("export_ref", name="uq_erp_stub_exports_ref"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_erp_stub_exports_tenant_status",
        "erp_stub_exports",
        ["tenant_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "erp_stub_export_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("export_id", GUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_json", JSON_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["export_id"], [f"{DB_SCHEMA}.erp_stub_exports.id"], ondelete="CASCADE"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_erp_stub_export_items_export",
        "erp_stub_export_items",
        ["export_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("erp_stub_export_items", schema=DB_SCHEMA)
    op.drop_table("erp_stub_exports", schema=DB_SCHEMA)
    op.drop_table("bank_stub_statement_lines", schema=DB_SCHEMA)
    op.drop_table("bank_stub_statements", schema=DB_SCHEMA)
    op.drop_table("bank_stub_payments", schema=DB_SCHEMA)
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS erp_stub_export_type"))
        op.execute(sa.text("DROP TYPE IF EXISTS erp_stub_export_status"))
        op.execute(sa.text("DROP TYPE IF EXISTS bank_stub_payment_status"))
