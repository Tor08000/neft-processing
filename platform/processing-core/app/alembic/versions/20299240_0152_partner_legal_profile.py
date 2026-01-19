"""Partner legal profile tables

Revision ID: 20299240_0152_partner_legal_profile
Revises: 20299230_0151_partner_finance_v1
Create Date: 2025-03-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    column_exists,
    create_index_if_not_exists,
    create_unique_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20299240_0152_partner_legal_profile"
down_revision = "20299230_0151_partner_finance_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

LEGAL_TYPES = ["INDIVIDUAL", "IP", "LEGAL_ENTITY"]
TAX_REGIMES = ["USN", "OSNO", "SELF_EMPLOYED", "FOREIGN", "OTHER"]
LEGAL_STATUSES = ["DRAFT", "PENDING_REVIEW", "VERIFIED", "BLOCKED"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "partner_legal_type", LEGAL_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "partner_tax_regime", TAX_REGIMES, schema=SCHEMA)
    ensure_pg_enum(bind, "partner_legal_status", LEGAL_STATUSES, schema=SCHEMA)

    legal_type_enum = safe_enum(bind, "partner_legal_type", LEGAL_TYPES, schema=SCHEMA)
    tax_regime_enum = safe_enum(bind, "partner_tax_regime", TAX_REGIMES, schema=SCHEMA)
    legal_status_enum = safe_enum(bind, "partner_legal_status", LEGAL_STATUSES, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "partner_legal_profiles",
        sa.Column("partner_id", sa.String(length=64), primary_key=True),
        sa.Column("legal_type", legal_type_enum, nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("tax_residency", sa.String(length=2), nullable=True),
        sa.Column("tax_regime", tax_regime_enum, nullable=True),
        sa.Column("vat_applicable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("legal_status", legal_status_enum, nullable=False, server_default=LEGAL_STATUSES[0]),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_legal_details",
        sa.Column("partner_id", sa.String(length=64), primary_key=True),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("inn", sa.String(length=32), nullable=True),
        sa.Column("kpp", sa.String(length=32), nullable=True),
        sa.Column("ogrn", sa.String(length=32), nullable=True),
        sa.Column("passport", sa.String(length=128), nullable=True),
        sa.Column("bank_account", sa.String(length=64), nullable=True),
        sa.Column("bank_bic", sa.String(length=32), nullable=True),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_tax_policies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("legal_type", legal_type_enum, nullable=False),
        sa.Column("tax_regime", tax_regime_enum, nullable=False),
        sa.Column("income_tax_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("withholding_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_legal_packs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("partner_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("pack_hash", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_partner_legal_packs_partner_created",
        "partner_legal_packs",
        ["partner_id", "created_at"],
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_partner_tax_policy",
        "partner_tax_policies",
        ["legal_type", "tax_regime"],
        schema=SCHEMA,
    )

    if not column_exists(bind, "partner_invoices", "tax_context", schema=SCHEMA):
        op.add_column("partner_invoices", sa.Column("tax_context", sa.JSON(), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "partner_acts", "tax_context", schema=SCHEMA):
        op.add_column("partner_acts", sa.Column("tax_context", sa.JSON(), nullable=True), schema=SCHEMA)

    _seed_tax_policies(bind)


def _seed_tax_policies(bind) -> None:
    if bind.dialect.name == "sqlite":
        return
    schema_prefix = f"{SCHEMA}." if SCHEMA else ""
    op.execute(
        sa.text(
            f"""
            INSERT INTO {schema_prefix}partner_tax_policies
            (id, legal_type, tax_regime, income_tax_rate, vat_rate, withholding_required, notes)
            VALUES
              (gen_random_uuid(), 'INDIVIDUAL', 'SELF_EMPLOYED', 4, 0, false, '4%/6% depending on payer'),
              (gen_random_uuid(), 'IP', 'USN', 6, 0, false, 'Simplified tax regime'),
              (gen_random_uuid(), 'LEGAL_ENTITY', 'OSNO', 20, 20, false, 'VAT + profit tax (info)')
            ON CONFLICT (legal_type, tax_regime) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if column_exists(bind, "partner_invoices", "tax_context", schema=SCHEMA):
        op.drop_column("partner_invoices", "tax_context", schema=SCHEMA)
    if column_exists(bind, "partner_acts", "tax_context", schema=SCHEMA):
        op.drop_column("partner_acts", "tax_context", schema=SCHEMA)

    op.drop_index("ix_partner_legal_packs_partner_created", table_name="partner_legal_packs", schema=SCHEMA)
    op.drop_table("partner_legal_packs", schema=SCHEMA)
    op.drop_table("partner_tax_policies", schema=SCHEMA)
    op.drop_table("partner_legal_details", schema=SCHEMA)
    op.drop_table("partner_legal_profiles", schema=SCHEMA)

    # enums are left in place for safety across deployments
