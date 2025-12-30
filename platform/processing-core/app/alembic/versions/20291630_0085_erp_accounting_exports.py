"""ERP accounting export mapping and reconciliation tables.

Revision ID: 20291630_0085_erp_accounting_exports
Revises: 20291620_0084_document_edo_status
Create Date: 2025-02-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.alembic.utils import (
    SCHEMA,
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
    table_exists,
)
from app.db.types import GUID


# revision identifiers, used by Alembic.
revision = "20291630_0085_erp_accounting_exports"
down_revision = "20291620_0084_document_edo_status"
branch_labels = None
depends_on = None


ERP_SYSTEM_TYPE = ["1C", "SAP", "GENERIC"]
ERP_EXPORT_FORMAT = ["CSV", "JSON", "XML_1C"]
ERP_DELIVERY_MODE = ["S3_PULL", "WEBHOOK_PUSH", "SFTP_PUSH", "API_PUSH"]
ERP_MAPPING_STATUS = ["DRAFT", "ACTIVE", "ARCHIVED"]
ERP_MAPPING_MATCH_KIND = [
    "DOC_TYPE",
    "SERVICE_CODE",
    "PRODUCT_TYPE",
    "COMMISSION_KIND",
    "TAX_RATE",
    "PARTNER",
    "CUSTOM",
]
ERP_COUNTERPARTY_REF_MODE = ["INN_KPP", "ERP_ID", "NAME"]
ERP_RECONCILIATION_STATUS = ["REQUESTED", "IN_PROGRESS", "OK", "MISMATCH", "FAILED"]
ERP_RECONCILIATION_VERDICT = [
    "OK",
    "MISSING_IN_ERP",
    "EXTRA_IN_ERP",
    "AMOUNT_DIFF",
    "TAX_DIFF",
]

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade():
    bind = op.get_bind()

    ensure_pg_enum(bind, "erp_system_type", ERP_SYSTEM_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "erp_export_format", ERP_EXPORT_FORMAT, schema=SCHEMA)
    ensure_pg_enum(bind, "erp_delivery_mode", ERP_DELIVERY_MODE, schema=SCHEMA)
    ensure_pg_enum(bind, "erp_mapping_status", ERP_MAPPING_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "erp_mapping_match_kind", ERP_MAPPING_MATCH_KIND, schema=SCHEMA)
    ensure_pg_enum(bind, "erp_counterparty_ref_mode", ERP_COUNTERPARTY_REF_MODE, schema=SCHEMA)
    ensure_pg_enum(bind, "erp_reconciliation_status", ERP_RECONCILIATION_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "erp_reconciliation_verdict", ERP_RECONCILIATION_VERDICT, schema=SCHEMA)

    if not table_exists(bind, "erp_export_profiles", schema=SCHEMA):
        system_type = safe_enum(bind, "erp_system_type", ERP_SYSTEM_TYPE, schema=SCHEMA)
        export_format = safe_enum(bind, "erp_export_format", ERP_EXPORT_FORMAT, schema=SCHEMA)
        delivery_mode = safe_enum(bind, "erp_delivery_mode", ERP_DELIVERY_MODE, schema=SCHEMA)
        create_table_if_not_exists(
            bind,
            "erp_export_profiles",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("client_id", sa.String(64), nullable=True),
            sa.Column("system_type", system_type, nullable=False),
            sa.Column("format", export_format, nullable=False),
            sa.Column("mapping_id", GUID(), nullable=True),
            sa.Column("delivery_mode", delivery_mode, nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("meta", JSON_TYPE, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_erp_export_profiles_tenant",
            "erp_export_profiles",
            ["tenant_id"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_erp_export_profiles_client",
            "erp_export_profiles",
            ["client_id"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "erp_mappings", schema=SCHEMA):
        system_type = safe_enum(bind, "erp_system_type", ERP_SYSTEM_TYPE, schema=SCHEMA)
        mapping_status = safe_enum(bind, "erp_mapping_status", ERP_MAPPING_STATUS, schema=SCHEMA)
        create_table_if_not_exists(
            bind,
            "erp_mappings",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("client_id", sa.String(64), nullable=True),
            sa.Column("system_type", system_type, nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", mapping_status, nullable=False),
            sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("meta", JSON_TYPE, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=SCHEMA,
        )
        create_index_if_not_exists(bind, "ix_erp_mappings_tenant", "erp_mappings", ["tenant_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_erp_mappings_client", "erp_mappings", ["client_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_erp_mappings_status", "erp_mappings", ["status"], schema=SCHEMA)

    if not table_exists(bind, "erp_mapping_rules", schema=SCHEMA):
        match_kind = safe_enum(bind, "erp_mapping_match_kind", ERP_MAPPING_MATCH_KIND, schema=SCHEMA)
        ref_mode = safe_enum(bind, "erp_counterparty_ref_mode", ERP_COUNTERPARTY_REF_MODE, schema=SCHEMA)
        create_table_if_not_exists(
            bind,
            "erp_mapping_rules",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("mapping_id", GUID(), nullable=False),
            sa.Column("match_kind", match_kind, nullable=False),
            sa.Column("match_value", sa.Text(), nullable=False),
            sa.Column("gl_account", sa.String(64), nullable=False),
            sa.Column("subaccount_1", sa.String(64), nullable=True),
            sa.Column("subaccount_2", sa.String(64), nullable=True),
            sa.Column("subaccount_3", sa.String(64), nullable=True),
            sa.Column("cost_item", sa.String(128), nullable=True),
            sa.Column("vat_code", sa.String(64), nullable=True),
            sa.Column("counterparty_ref_mode", ref_mode, nullable=True),
            sa.Column("nomenclature_ref", sa.String(128), nullable=True),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_erp_mapping_rules_mapping_priority",
            "erp_mapping_rules",
            ["mapping_id", "priority"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "erp_reconciliation_runs", schema=SCHEMA):
        system_type = safe_enum(bind, "erp_system_type", ERP_SYSTEM_TYPE, schema=SCHEMA)
        rec_status = safe_enum(bind, "erp_reconciliation_status", ERP_RECONCILIATION_STATUS, schema=SCHEMA)
        create_table_if_not_exists(
            bind,
            "erp_reconciliation_runs",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("client_id", sa.String(64), nullable=True),
            sa.Column("export_batch_id", sa.String(36), nullable=False),
            sa.Column("system_type", system_type, nullable=False),
            sa.Column("status", rec_status, nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metrics", JSON_TYPE, nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_erp_reconciliation_runs_batch",
            "erp_reconciliation_runs",
            ["export_batch_id"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "erp_reconciliation_items", schema=SCHEMA):
        verdict = safe_enum(bind, "erp_reconciliation_verdict", ERP_RECONCILIATION_VERDICT, schema=SCHEMA)
        create_table_if_not_exists(
            bind,
            "erp_reconciliation_items",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("run_id", GUID(), nullable=False),
            sa.Column("item_key", sa.String(128), nullable=False),
            sa.Column("verdict", verdict, nullable=False),
            sa.Column("diff", JSON_TYPE, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_erp_reconciliation_items_run",
            "erp_reconciliation_items",
            ["run_id"],
            schema=SCHEMA,
        )

    if column_exists(bind, "accounting_export_batches", "erp_profile_id", schema=SCHEMA) is False:
        op.add_column(
            "accounting_export_batches",
            sa.Column("erp_profile_id", GUID(), nullable=True),
            schema=SCHEMA,
        )
    if column_exists(bind, "accounting_export_batches", "erp_system_type", schema=SCHEMA) is False:
        erp_system = safe_enum(bind, "erp_system_type", ERP_SYSTEM_TYPE, schema=SCHEMA)
        op.add_column(
            "accounting_export_batches",
            sa.Column("erp_system_type", erp_system, nullable=True),
            schema=SCHEMA,
        )
    if column_exists(bind, "accounting_export_batches", "erp_mapping_id", schema=SCHEMA) is False:
        op.add_column(
            "accounting_export_batches",
            sa.Column("erp_mapping_id", GUID(), nullable=True),
            schema=SCHEMA,
        )
    if column_exists(bind, "accounting_export_batches", "erp_mapping_version", schema=SCHEMA) is False:
        op.add_column(
            "accounting_export_batches",
            sa.Column("erp_mapping_version", sa.Integer(), nullable=True),
            schema=SCHEMA,
        )


def downgrade():
    bind = op.get_bind()

    if table_exists(bind, "erp_reconciliation_items", schema=SCHEMA):
        op.drop_table("erp_reconciliation_items", schema=SCHEMA)
    if table_exists(bind, "erp_reconciliation_runs", schema=SCHEMA):
        op.drop_table("erp_reconciliation_runs", schema=SCHEMA)
    if table_exists(bind, "erp_mapping_rules", schema=SCHEMA):
        op.drop_table("erp_mapping_rules", schema=SCHEMA)
    if table_exists(bind, "erp_mappings", schema=SCHEMA):
        op.drop_table("erp_mappings", schema=SCHEMA)
    if table_exists(bind, "erp_export_profiles", schema=SCHEMA):
        op.drop_table("erp_export_profiles", schema=SCHEMA)

    if column_exists(bind, "accounting_export_batches", "erp_profile_id", schema=SCHEMA):
        op.drop_column("accounting_export_batches", "erp_profile_id", schema=SCHEMA)
    if column_exists(bind, "accounting_export_batches", "erp_system_type", schema=SCHEMA):
        op.drop_column("accounting_export_batches", "erp_system_type", schema=SCHEMA)
    if column_exists(bind, "accounting_export_batches", "erp_mapping_id", schema=SCHEMA):
        op.drop_column("accounting_export_batches", "erp_mapping_id", schema=SCHEMA)
    if column_exists(bind, "accounting_export_batches", "erp_mapping_version", schema=SCHEMA):
        op.drop_column("accounting_export_batches", "erp_mapping_version", schema=SCHEMA)
