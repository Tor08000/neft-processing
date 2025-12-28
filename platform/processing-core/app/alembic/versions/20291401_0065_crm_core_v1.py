"""crm core v1 tables and enums

Revision ID: 20291401_0065_crm_core_v1
Revises: 20291335_0064_logistics_fuel_link_unique
Create Date: 2029-04-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import ensure_pg_enum, table_exists
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

# revision identifiers, used by Alembic.
revision = "20291401_0065_crm_core_v1"
down_revision = "20291335_0064_logistics_fuel_link_unique"
branch_labels = None
depends_on = None


CRM_CLIENT_STATUS = ["ACTIVE", "SUSPENDED", "CLOSED"]
CRM_CONTRACT_STATUS = ["DRAFT", "ACTIVE", "PAUSED", "TERMINATED"]
CRM_BILLING_MODE = ["POSTPAID", "PREPAID"]
CRM_TARIFF_STATUS = ["ACTIVE", "ARCHIVED"]
CRM_BILLING_PERIOD = ["MONTHLY", "YEARLY"]
CRM_SUBSCRIPTION_STATUS = ["ACTIVE", "PAST_DUE", "SUSPENDED", "CANCELLED"]
CRM_PROFILE_STATUS = ["ACTIVE", "ARCHIVED"]
CRM_FEATURE_FLAG = [
    "FUEL_ENABLED",
    "LOGISTICS_ENABLED",
    "DOCUMENTS_ENABLED",
    "RISK_BLOCKING_ENABLED",
    "ACCOUNTING_EXPORT_ENABLED",
]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "crm_client_status", CRM_CLIENT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_contract_status", CRM_CONTRACT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_billing_mode", CRM_BILLING_MODE, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_tariff_status", CRM_TARIFF_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_billing_period", CRM_BILLING_PERIOD, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_subscription_status", CRM_SUBSCRIPTION_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_profile_status", CRM_PROFILE_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_feature_flag", CRM_FEATURE_FLAG, schema=SCHEMA)

    if not table_exists(bind, "crm_clients", schema=SCHEMA):
        op.create_table(
            "crm_clients",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("legal_name", sa.String(256), nullable=False),
            sa.Column("tax_id", sa.String(32), nullable=True),
            sa.Column("kpp", sa.String(32), nullable=True),
            sa.Column("country", sa.String(2), nullable=False),
            sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Moscow"),
            sa.Column("status", sa.Enum(*CRM_CLIENT_STATUS, name="crm_client_status"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("meta", sa.JSON, nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "id", name="uq_crm_clients_tenant_id"),
            schema=SCHEMA,
        )
        op.create_index("ix_crm_clients_tenant", "crm_clients", ["tenant_id"], schema=SCHEMA)

    if not table_exists(bind, "crm_limit_profiles", schema=SCHEMA):
        op.create_table(
            "crm_limit_profiles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("status", sa.Enum(*CRM_PROFILE_STATUS, name="crm_profile_status"), nullable=False),
            sa.Column("definition", sa.JSON, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index("ix_crm_limit_profiles_tenant", "crm_limit_profiles", ["tenant_id"], schema=SCHEMA)

    if not table_exists(bind, "crm_risk_profiles", schema=SCHEMA):
        op.create_table(
            "crm_risk_profiles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("status", sa.Enum(*CRM_PROFILE_STATUS, name="crm_profile_status"), nullable=False),
            sa.Column("risk_policy_id", sa.String(64), nullable=False),
            sa.Column("threshold_set_id", sa.String(64), nullable=True),
            sa.Column("shadow_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("meta", sa.JSON, nullable=True),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index("ix_crm_risk_profiles_tenant", "crm_risk_profiles", ["tenant_id"], schema=SCHEMA)

    if not table_exists(bind, "crm_contracts", schema=SCHEMA):
        op.create_table(
            "crm_contracts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), sa.ForeignKey(f"{SCHEMA}.crm_clients.id"), nullable=False),
            sa.Column("contract_number", sa.String(128), nullable=False),
            sa.Column("status", sa.Enum(*CRM_CONTRACT_STATUS, name="crm_contract_status"), nullable=False),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("billing_mode", sa.Enum(*CRM_BILLING_MODE, name="crm_billing_mode"), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("risk_profile_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.crm_risk_profiles.id"), nullable=True),
            sa.Column("limit_profile_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.crm_limit_profiles.id"), nullable=True),
            sa.Column("documents_required", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("meta", sa.JSON, nullable=True),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index("ix_crm_contracts_client_status", "crm_contracts", ["client_id", "status"], schema=SCHEMA)

    if not table_exists(bind, "crm_tariff_plans", schema=SCHEMA):
        op.create_table(
            "crm_tariff_plans",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.String(512), nullable=True),
            sa.Column("status", sa.Enum(*CRM_TARIFF_STATUS, name="crm_tariff_status"), nullable=False),
            sa.Column("billing_period", sa.Enum(*CRM_BILLING_PERIOD, name="crm_billing_period"), nullable=False),
            sa.Column("base_fee_minor", sa.BigInteger, nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("features", sa.JSON, nullable=True),
            sa.Column("limits_defaults", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )

    if not table_exists(bind, "crm_subscriptions", schema=SCHEMA):
        op.create_table(
            "crm_subscriptions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), sa.ForeignKey(f"{SCHEMA}.crm_clients.id"), nullable=False),
            sa.Column("tariff_id", sa.String(64), sa.ForeignKey(f"{SCHEMA}.crm_tariff_plans.id"), nullable=False),
            sa.Column("status", sa.Enum(*CRM_SUBSCRIPTION_STATUS, name="crm_subscription_status"), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("renew_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_invoice_period_id", sa.String(64), nullable=True),
            sa.Column("meta", sa.JSON, nullable=True),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index("ix_crm_subscriptions_client", "crm_subscriptions", ["client_id"], schema=SCHEMA)
        op.create_index("ix_crm_subscriptions_tenant", "crm_subscriptions", ["tenant_id"], schema=SCHEMA)

    if not table_exists(bind, "crm_feature_flags", schema=SCHEMA):
        op.create_table(
            "crm_feature_flags",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), sa.ForeignKey(f"{SCHEMA}.crm_clients.id"), nullable=False),
            sa.Column("feature", sa.Enum(*CRM_FEATURE_FLAG, name="crm_feature_flag"), nullable=False),
            sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_by", sa.String(64), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "client_id", "feature", name="uq_crm_feature_flag"),
            schema=SCHEMA,
        )
        op.create_index("ix_crm_feature_flags_client", "crm_feature_flags", ["client_id"], schema=SCHEMA)


def downgrade() -> None:
    # Intentionally omitted for additive migration.
    pass
