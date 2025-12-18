"""Bootstrap schema for clean databases

Revision ID: 20270601_0024_bootstrap_schema
Revises: 20270520_0023_billing_summary_status_enum_fix
Create Date: 2027-06-01 00:24:00
"""
from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
)

# revision identifiers, used by Alembic.
revision = "20270601_0024_bootstrap_schema"
down_revision = "20270520_0023_billing_summary_status_enum_fix"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DB_SCHEMA", "public")


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



def _uuid_type(bind):
    return postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)



def _json_type(bind):
    return postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()



def upgrade() -> None:
    bind = op.get_bind()

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
    ensure_pg_enum(bind, "limitwindow", LIMIT_WINDOW_VALUES)

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

    uuid_type = _uuid_type(bind)
    json_type = _json_type(bind)

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

    create_table_if_not_exists(
        bind,
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
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("terminal_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("card_id", sa.String(length=64), nullable=False),
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

    create_table_if_not_exists(
        bind,
        "accounts",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("card_id", sa.String(length=64), sa.ForeignKey("cards.id"), nullable=True),
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

    create_table_if_not_exists(
        bind,
        "account_balances",
        sa.Column("account_id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
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

    create_table_if_not_exists(
        bind,
        "ledger_entries",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_id", uuid_type, sa.ForeignKey("operations.operation_id", ondelete="SET NULL"), nullable=True),
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

    for table_name in ("merchants", "clients", "operations"):
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
