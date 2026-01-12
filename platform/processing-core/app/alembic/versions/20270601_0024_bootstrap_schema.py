"""Bootstrap schema for clean databases

Revision ID: 20270601_0024_bootstrap_schema
Revises: 20270520_0023_billing_summary_status_enum_fix
Create Date: 2027-06-01 00:24:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import (
    ALEMBIC_VERSION_TABLE,
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20270601_0024_bootstrap_schema"
down_revision = "20270520_0023_billing_summary_status_enum_fix"
branch_labels = None
depends_on = None

SCHEMA_RESOLUTION = resolve_db_schema()
SCHEMA = SCHEMA_RESOLUTION.schema


ACCOUNT_TYPE_VALUES = ["CLIENT_MAIN", "CLIENT_CREDIT", "CARD_LIMIT", "TECHNICAL"]
ACCOUNT_STATUS_VALUES = ["ACTIVE", "FROZEN", "CLOSED"]
LEDGER_DIRECTION_VALUES = ["DEBIT", "CREDIT"]

RISK_RULE_SCOPE_VALUES = ["GLOBAL", "CLIENT", "CARD", "TARIFF", "SEGMENT"]
RISK_RULE_ACTION_VALUES = [
    "HARD_DECLINE",
    "SOFT_FLAG",
    "TARIFF_LIMIT",
    "LOW",
    "MEDIUM",
    "HIGH",
    "BLOCK",
    "MANUAL_REVIEW",
]
RISK_RULE_AUDIT_ACTION_VALUES = ["CREATE", "UPDATE", "ENABLE", "DISABLE"]

CLEARING_BATCH_STATUS_VALUES = ["PENDING", "SENT", "CONFIRMED", "FAILED"]
BILLING_SUMMARY_STATUS_VALUES = ["PENDING", "FINALIZED"]
PRODUCT_TYPE_VALUES = ["ACQUIRING", "PAYOUT", "SUBSCRIPTION"]
LIMIT_CONFIG_SCOPE_VALUES = ["GLOBAL", "CLIENT", "CARD", "TARIFF"]
LIMIT_WINDOW_VALUES = ["PER_TX", "DAILY", "MONTHLY"]
LIMIT_TYPE_VALUES = ["DAILY_VOLUME", "DAILY_AMOUNT", "MONTHLY_AMOUNT", "CREDIT_LIMIT"]
COMMISSION_RATE_TYPE_VALUES = ["PLATFORM", "PARTNER", "PROMO"]



def _uuid_type(bind):
    return postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)



def _json_type(bind):
    return postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name, schema=SCHEMA)


def _ensure_schema(bind) -> None:
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return

    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))


def upgrade() -> None:
    bind = op.get_bind()

    _ensure_schema(bind)

    ensure_pg_enum(bind, "accounttype", ACCOUNT_TYPE_VALUES)
    ensure_pg_enum(bind, "accountstatus", ACCOUNT_STATUS_VALUES)
    ensure_pg_enum(bind, "ledgerdirection", LEDGER_DIRECTION_VALUES)
    ensure_pg_enum(bind, "riskrulescope", RISK_RULE_SCOPE_VALUES)
    ensure_pg_enum(bind, "riskruleaction", RISK_RULE_ACTION_VALUES)
    ensure_pg_enum(bind, "riskruleauditaction", RISK_RULE_AUDIT_ACTION_VALUES)
    ensure_pg_enum(bind, "clearing_status", ["PENDING"])
    ensure_pg_enum(bind, "clearing_batch_status", CLEARING_BATCH_STATUS_VALUES)
    ensure_pg_enum(bind, "billing_summary_status", BILLING_SUMMARY_STATUS_VALUES)
    ensure_pg_enum(bind, "product_type", PRODUCT_TYPE_VALUES)
    ensure_pg_enum(bind, "limitconfigscope", LIMIT_CONFIG_SCOPE_VALUES)
    ensure_pg_enum(bind, "limittype", LIMIT_TYPE_VALUES)
    ensure_pg_enum(bind, "limitwindow", LIMIT_WINDOW_VALUES)
    ensure_pg_enum(bind, "commission_rate_type", COMMISSION_RATE_TYPE_VALUES)

    account_type_enum = safe_enum(bind, "accounttype", ACCOUNT_TYPE_VALUES)
    account_status_enum = safe_enum(bind, "accountstatus", ACCOUNT_STATUS_VALUES)
    ledger_direction_enum = safe_enum(bind, "ledgerdirection", LEDGER_DIRECTION_VALUES)
    risk_rule_scope_enum = safe_enum(bind, "riskrulescope", RISK_RULE_SCOPE_VALUES)
    risk_rule_action_enum = safe_enum(bind, "riskruleaction", RISK_RULE_ACTION_VALUES)
    risk_rule_audit_enum = safe_enum(bind, "riskruleauditaction", RISK_RULE_AUDIT_ACTION_VALUES)
    clearing_status_enum = safe_enum(bind, "clearing_status", ["PENDING"])
    clearing_batch_status_enum = safe_enum(
        bind, "clearing_batch_status", CLEARING_BATCH_STATUS_VALUES
    )
    billing_status_enum = safe_enum(bind, "billing_summary_status", BILLING_SUMMARY_STATUS_VALUES)
    product_type_enum = safe_enum(bind, "product_type", PRODUCT_TYPE_VALUES)
    limit_config_scope_enum = safe_enum(bind, "limitconfigscope", LIMIT_CONFIG_SCOPE_VALUES)
    limit_type_enum = safe_enum(bind, "limittype", LIMIT_TYPE_VALUES)
    limit_window_enum = safe_enum(bind, "limitwindow", LIMIT_WINDOW_VALUES)
    commission_rate_type_enum = safe_enum(bind, "commission_rate_type", COMMISSION_RATE_TYPE_VALUES)

    uuid_type = _uuid_type(bind)
    json_type = _json_type(bind)

    if not _table_exists(bind, "tariff_plans"):
        op.create_table(
            "tariff_plans",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("params", json_type, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
    create_index_if_not_exists(
        bind, "ix_tariff_plans_name", "tariff_plans", ["name"], unique=True, schema=SCHEMA
    )

    if not _table_exists(bind, "client_tariffs"):
        op.create_table(
            "client_tariffs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("client_id", sa.String(length=64), nullable=False),
            sa.Column("tariff_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.tariff_plans.id"), nullable=False),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()") if bind.dialect.name == "postgresql" else None,
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            schema=SCHEMA,
        )
    for index_name, columns, unique in (
        ("ix_client_tariffs_client_id", ["client_id"], False),
        ("ix_client_tariffs_tariff_id", ["tariff_id"], False),
        ("ix_client_tariffs_valid_from", ["valid_from"], False),
        ("ix_client_tariffs_valid_to", ["valid_to"], False),
        ("ix_client_tariffs_priority", ["priority"], False),
    ):
        create_index_if_not_exists(bind, index_name, "client_tariffs", columns, schema=SCHEMA, unique=unique)

    create_table_if_not_exists(
        bind,
        "tariff_prices",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("tariff_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.tariff_plans.id"), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("partner_id", sa.String(length=64), nullable=True),
        sa.Column("azs_id", sa.String(length=64), nullable=True),
        sa.Column("price_per_liter", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_price_per_liter", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()") if bind.dialect.name == "postgresql" else None,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_tariff_prices_tariff_id": ["tariff_id"],
        "ix_tariff_prices_product_id": ["product_id"],
        "ix_tariff_prices_partner_id": ["partner_id"],
        "ix_tariff_prices_azs_id": ["azs_id"],
        "ix_tariff_prices_valid_from": ["valid_from"],
        "ix_tariff_prices_valid_to": ["valid_to"],
        "ix_tariff_prices_priority": ["priority"],
    }.items():
        create_index_if_not_exists(bind, index_name, "tariff_prices", columns, unique=False, schema=SCHEMA)

    if not _table_exists(bind, "commission_rules"):
        op.create_table(
            "commission_rules",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tariff_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.tariff_plans.id"), nullable=False),
            sa.Column("product_id", sa.String(length=64), nullable=True),
            sa.Column("partner_id", sa.String(length=64), nullable=True),
            sa.Column("azs_id", sa.String(length=64), nullable=True),
            sa.Column("platform_rate", sa.Numeric(6, 4), nullable=False),
            sa.Column("partner_rate", sa.Numeric(6, 4), nullable=True),
            sa.Column("promo_rate", sa.Numeric(6, 4), nullable=True),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()") if bind.dialect.name == "postgresql" else None,
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            schema=SCHEMA,
        )
    for index_name, columns in {
        "ix_commission_rules_tariff_id": ["tariff_id"],
        "ix_commission_rules_product_id": ["product_id"],
        "ix_commission_rules_partner_id": ["partner_id"],
        "ix_commission_rules_azs_id": ["azs_id"],
        "ix_commission_rules_valid_from": ["valid_from"],
        "ix_commission_rules_valid_to": ["valid_to"],
        "ix_commission_rules_priority": ["priority"],
    }.items():
        create_index_if_not_exists(bind, index_name, "commission_rules", columns, unique=False, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "clients",
        sa.Column(
            "id",
            uuid_type,
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()") if bind.dialect.name == "postgresql" else None,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("inn", sa.String(), nullable=True),
        sa.Column("tariff_plan", sa.String(), nullable=True),
        sa.Column("account_manager", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()") if bind.dialect.name == "postgresql" else None,
            nullable=False,
        ),
        sa.UniqueConstraint("external_id", name="uq_clients_external_id"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_clients_id", "clients", ["id"], unique=False, schema=SCHEMA
    )

    create_table_if_not_exists(
        bind,
        "merchants",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_merchants_id", "merchants", ["id"], unique=False, schema=SCHEMA
    )
    create_index_if_not_exists(
        bind,
        "ix_merchants_status",
        "merchants",
        ["status"],
        unique=False,
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "terminals",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("merchant_id", sa.String(length=64), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_terminals_id", "terminals", ["id"], unique=False, schema=SCHEMA
    )
    create_index_if_not_exists(
        bind,
        "ix_terminals_merchant_id",
        "terminals",
        ["merchant_id"],
        unique=False,
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_terminals_status",
        "terminals",
        ["status"],
        unique=False,
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "cards",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("pan_masked", sa.String(length=32), nullable=True),
        sa.Column("expires_at", sa.String(length=16), nullable=True),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_cards_id", "cards", ["id"], unique=False, schema=SCHEMA
    )
    create_index_if_not_exists(
        bind, "ix_cards_client_id", "cards", ["client_id"], unique=False, schema=SCHEMA
    )
    create_index_if_not_exists(
        bind, "ix_cards_status", "cards", ["status"], unique=False, schema=SCHEMA
    )

    create_table_if_not_exists(
        bind,
        "partners",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("allowed_ips", json_type, nullable=True, server_default=sa.text("'[]'::jsonb") if bind.dialect.name == "postgresql" else None),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_partners_status", "partners", ["status"], unique=False, schema=SCHEMA
    )

    if not _table_exists(bind, "operations"):
        op.create_table(
            "operations",
            sa.Column("operation_id", sa.String(length=64), primary_key=True, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()") if bind.dialect.name == "postgresql" else None,
                nullable=False,
            ),
            sa.Column("operation_type", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("merchant_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.merchants.id"), nullable=False),
            sa.Column("terminal_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.terminals.id"), nullable=False),
            sa.Column("client_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.clients.id"), nullable=False),
            sa.Column("card_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.cards.id"), nullable=False),
            sa.Column("accounts", json_type, nullable=True),
            sa.Column("posting_result", json_type, nullable=True),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("authorized", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("response_code", sa.String(length=16), nullable=False),
            sa.Column("response_message", sa.String(length=255), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("daily_limit", sa.BigInteger(), nullable=True),
            sa.Column("limit_per_tx", sa.BigInteger(), nullable=True),
            sa.Column("used_today", sa.BigInteger(), nullable=True),
            sa.Column("new_used_today", sa.BigInteger(), nullable=True),
            sa.Column("parent_operation_id", sa.String(length=64), nullable=True),
            sa.Column("mcc", sa.String(length=32), nullable=True),
            sa.Column("product_code", sa.String(length=64), nullable=True),
            sa.Column("product_category", sa.String(length=64), nullable=True),
            sa.Column("tx_type", sa.String(length=32), nullable=True),
            sa.Column("captured_amount", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("refunded_amount", sa.BigInteger(), nullable=False, server_default="0"),
            schema=SCHEMA,
        )
    for index_name, columns in {
        "ix_operations_card_id": ["card_id"],
        "ix_operations_client_id": ["client_id"],
        "ix_operations_merchant_id": ["merchant_id"],
        "ix_operations_terminal_id": ["terminal_id"],
        "ix_operations_created_at": ["created_at"],
        "ix_operations_mcc": ["mcc"],
        "ix_operations_product_category": ["product_category"],
        "ix_operations_tx_type": ["tx_type"],
        "ix_operations_operation_id": ["operation_id"],
        "ix_operations_operation_type": ["operation_type"],
        "ix_operations_status": ["status"],
        "ix_operations_parent_operation_id": ["parent_operation_id"],
    }.items():
        create_index_if_not_exists(
            bind, index_name, "operations", columns, unique=False, schema=SCHEMA
        )

    create_table_if_not_exists(
        bind,
        "billing_summary",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("billing_date", sa.Date(), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("product_type", product_type_enum, nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("operations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_quantity", sa.Numeric(18, 3), nullable=True),
        sa.Column("commission_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()") if bind.dialect.name == "postgresql" else None,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "billing_date",
            "merchant_id",
            "client_id",
            "product_type",
            "currency",
            name="uq_billing_summary_unique_scope",
        ),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_billing_summary_billing_date",
        "billing_summary",
        ["billing_date"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_billing_summary_merchant_id", "billing_summary", ["merchant_id"], schema=SCHEMA
    )
    create_index_if_not_exists(
        bind, "ix_billing_summary_client_id", "billing_summary", ["client_id"], schema=SCHEMA
    )
    create_index_if_not_exists(
        bind,
        "ix_billing_summary_product_type",
        "billing_summary",
        ["product_type"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_billing_summary_currency", "billing_summary", ["currency"], schema=SCHEMA
    )

    create_table_if_not_exists(
        bind,
        "clearing",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_date", sa.Date(), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_amount", sa.BigInteger(), nullable=False),
        sa.Column("status", clearing_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("details", json_type, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "batch_date", "merchant_id", "currency", name="uq_clearing_date_merchant_currency"
        ),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_clearing_batch_date", "clearing", ["batch_date"], schema=SCHEMA
    )
    create_index_if_not_exists(
        bind, "ix_clearing_merchant_id", "clearing", ["merchant_id"], schema=SCHEMA
    )
    create_index_if_not_exists(
        bind, "ix_clearing_currency", "clearing", ["currency"], schema=SCHEMA
    )
    create_index_if_not_exists(
        bind, "ix_clearing_status", "clearing", ["status"], schema=SCHEMA
    )

    create_table_if_not_exists(
        bind,
        "clearing_batch",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Integer(), nullable=False),
        sa.Column("operations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", clearing_batch_status_enum, nullable=False, server_default="PENDING"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_clearing_batch_status", "clearing_batch", ["status"], schema=SCHEMA
    )
    create_index_if_not_exists(
        bind,
        "ix_clearing_batch_merchant_id",
        "clearing_batch",
        ["merchant_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_clearing_batch_date_from",
        "clearing_batch",
        ["date_from"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_clearing_batch_date_to", "clearing_batch", ["date_to"], schema=SCHEMA
    )

    create_table_if_not_exists(
        bind,
        "clearing_batch_operation",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), sa.ForeignKey("clearing_batch.id"), nullable=False),
        sa.Column("operation_id", sa.String(length=64), sa.ForeignKey("operations.operation_id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_clearing_batch_operation_batch_id",
        "clearing_batch_operation",
        ["batch_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "risk_rules",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope", risk_rule_scope_enum, nullable=False),
        sa.Column("subject_ref", sa.String(length=128), nullable=True),
        sa.Column("action", risk_rule_action_enum, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("dsl_payload", json_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_risk_rules_scope", "risk_rules", ["scope"], unique=False, schema=SCHEMA
    )
    create_index_if_not_exists(
        bind,
        "ix_risk_rules_subject_ref",
        "risk_rules",
        ["subject_ref"],
        unique=False,
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_risk_rules_enabled", "risk_rules", ["enabled"], unique=False, schema=SCHEMA
    )

    create_table_if_not_exists(
        bind,
        "risk_rule_versions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("rule_id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), sa.ForeignKey("risk_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("dsl_payload", json_type, nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("rule_id", "version", name="uq_risk_rule_version"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_risk_rule_versions_rule_id", "risk_rule_versions", ["rule_id"], unique=False, schema=SCHEMA
    )
    create_index_if_not_exists(
        bind,
        "ix_risk_rule_versions_effective_from",
        "risk_rule_versions",
        ["effective_from"],
        unique=False,
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "risk_rule_audits",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("rule_id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), sa.ForeignKey("risk_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", risk_rule_audit_enum, nullable=False),
        sa.Column("old_value", json_type, nullable=True),
        sa.Column("new_value", json_type, nullable=True),
        sa.Column("performed_by", sa.String(length=256), nullable=True),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_risk_rule_audits_rule_id", "risk_rule_audits", ["rule_id"], schema=SCHEMA
    )
    create_index_if_not_exists(
        bind, "ix_risk_rule_audits_action", "risk_rule_audits", ["action"], schema=SCHEMA
    )
    create_index_if_not_exists(
        bind,
        "ix_risk_rule_audits_performed_at",
        "risk_rule_audits",
        ["performed_at"],
        schema=SCHEMA,
    )

    if not _table_exists(bind, "accounts"):
        op.create_table(
            "accounts",
            sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
            sa.Column("client_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.clients.id"), nullable=False),
            sa.Column("card_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.cards.id"), nullable=True),
            sa.Column("tariff_id", sa.String(length=64), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("type", account_type_enum, nullable=False),
            sa.Column("status", account_status_enum, nullable=False, server_default="ACTIVE"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            schema=SCHEMA,
        )
    create_index_if_not_exists(
        bind, "ix_accounts_client_id", "accounts", ["client_id"], schema=SCHEMA
    )
    create_index_if_not_exists(
        bind, "ix_accounts_card_id", "accounts", ["card_id"], schema=SCHEMA
    )
    create_index_if_not_exists(bind, "ix_accounts_type", "accounts", ["type"], schema=SCHEMA)
    create_index_if_not_exists(
        bind, "ix_accounts_status", "accounts", ["status"], schema=SCHEMA
    )

    if not _table_exists(bind, "account_balances"):
        op.create_table(
            "account_balances",
            sa.Column(
                "account_id",
                sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                sa.ForeignKey(f"{SCHEMA}.accounts.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("current_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("available_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            schema=SCHEMA,
        )

    if not _table_exists(bind, "ledger_entries"):
        op.create_table(
            "ledger_entries",
            sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
            sa.Column(
                "account_id",
                sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                sa.ForeignKey(f"{SCHEMA}.accounts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "operation_id",
                uuid_type,
                sa.ForeignKey(f"{SCHEMA}.operations.operation_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("direction", ledger_direction_enum, nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("balance_after", sa.Numeric(18, 4), nullable=True),
            sa.Column(
                "posted_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("value_date", sa.Date(), nullable=True),
            schema=SCHEMA,
        )
    create_index_if_not_exists(
        bind, "ix_ledger_entries_account_id", "ledger_entries", ["account_id"], schema=SCHEMA
    )
    create_index_if_not_exists(
        bind,
        "ix_ledger_entries_operation_id",
        "ledger_entries",
        ["operation_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_ledger_entries_posted_at", "ledger_entries", ["posted_at"], schema=SCHEMA
    )

    if not _table_exists(bind, "limit_configs"):
        window_default = sa.text("'DAILY'::limitwindow") if bind.dialect.name == "postgresql" else sa.text("'DAILY'")

        op.create_table(
            "limit_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("scope", limit_config_scope_enum, nullable=False),
            sa.Column("subject_ref", sa.String(length=64), nullable=False),
            sa.Column("limit_type", limit_type_enum, nullable=False),
            sa.Column("value", sa.BigInteger(), nullable=False),
            sa.Column("window", limit_window_enum, nullable=False, server_default=window_default),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("tariff_plan_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.tariff_plans.id"), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )

    create_index_if_not_exists(bind, "ix_limit_configs_scope", "limit_configs", ["scope"], unique=False, schema=SCHEMA)
    create_index_if_not_exists(
        bind, "ix_limit_configs_subject", "limit_configs", ["subject_ref"], unique=False, schema=SCHEMA
    )
    create_index_if_not_exists(bind, "ix_limit_configs_enabled", "limit_configs", ["enabled"], unique=False, schema=SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_limit_configs_scope_subject_type",
        "limit_configs",
        ["scope", "subject_ref", "limit_type"],
        unique=False,
        schema=SCHEMA,
    )

    version_regclass = bind.exec_driver_sql(
        f"select to_regclass('{SCHEMA}.{ALEMBIC_VERSION_TABLE}')"
    ).scalar()
    if not version_regclass:
        raise RuntimeError(f"Bootstrap schema failed: missing {ALEMBIC_VERSION_TABLE}")

    for table_name in ("merchants", "clients", "operations", "accounts", "ledger_entries", "limit_configs"):
        exists = bind.exec_driver_sql(
            f"select to_regclass('{SCHEMA}.{table_name}')"
        ).scalar()
        if not exists:
            raise RuntimeError(f"Bootstrap schema failed: missing table {table_name}")


def downgrade() -> None:
    bind = op.get_bind()

    for index_name in (
        "ix_ledger_entries_posted_at",
        "ix_ledger_entries_operation_id",
        "ix_ledger_entries_account_id",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)
    for table_name in ("ledger_entries", "account_balances", "accounts"):
        drop_table_if_exists(bind, table_name, schema=SCHEMA)

    for index_name in (
        "ix_risk_rule_audits_performed_at",
        "ix_risk_rule_audits_action",
        "ix_risk_rule_audits_rule_id",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)
    drop_table_if_exists(bind, "risk_rule_audits", schema=SCHEMA)

    for index_name in (
        "ix_risk_rule_versions_effective_from",
        "ix_risk_rule_versions_rule_id",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)
    drop_table_if_exists(bind, "risk_rule_versions", schema=SCHEMA)

    for index_name in (
        "ix_risk_rules_enabled",
        "ix_risk_rules_subject_ref",
        "ix_risk_rules_scope",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)
    drop_table_if_exists(bind, "risk_rules", schema=SCHEMA)

    drop_index_if_exists(bind, "ix_clearing_batch_operation_batch_id", schema=SCHEMA)
    drop_table_if_exists(bind, "clearing_batch_operation", schema=SCHEMA)

    for index_name in (
        "ix_clearing_batch_date_to",
        "ix_clearing_batch_date_from",
        "ix_clearing_batch_merchant_id",
        "ix_clearing_batch_status",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)
    drop_table_if_exists(bind, "clearing_batch", schema=SCHEMA)

    for index_name in (
        "ix_clearing_status",
        "ix_clearing_currency",
        "ix_clearing_merchant_id",
        "ix_clearing_batch_date",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)
    drop_table_if_exists(bind, "clearing", schema=SCHEMA)

    for index_name in (
        "ix_billing_summary_currency",
        "ix_billing_summary_product_type",
        "ix_billing_summary_client_id",
        "ix_billing_summary_merchant_id",
        "ix_billing_summary_billing_date",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)
    drop_table_if_exists(bind, "billing_summary", schema=SCHEMA)

    for index_name in (
        "ix_operations_parent_operation_id",
        "ix_operations_status",
        "ix_operations_operation_type",
        "ix_operations_operation_id",
        "ix_operations_tx_type",
        "ix_operations_product_category",
        "ix_operations_mcc",
        "ix_operations_created_at",
        "ix_operations_terminal_id",
        "ix_operations_merchant_id",
        "ix_operations_client_id",
        "ix_operations_card_id",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)
    drop_table_if_exists(bind, "operations", schema=SCHEMA)

    for index_name in (
        "ix_partners_status",
        "ix_cards_status",
        "ix_cards_client_id",
        "ix_cards_id",
        "ix_terminals_status",
        "ix_terminals_merchant_id",
        "ix_terminals_id",
        "ix_merchants_status",
        "ix_merchants_id",
        "ix_clients_id",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)

    for table_name in (
        "partners",
        "cards",
        "terminals",
        "merchants",
        "clients",
    ):
        drop_table_if_exists(bind, table_name, schema=SCHEMA)
