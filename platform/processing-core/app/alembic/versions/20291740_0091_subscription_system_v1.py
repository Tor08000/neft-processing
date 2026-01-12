"""Subscription system v1 tables.

Revision ID: 20291740_0091_subscription_system_v1
Revises: 20291730_0090_cases_escalations
Create Date: 2025-03-06 00:00:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

import sqlalchemy as sa
from alembic import op

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20291740_0091_subscription_system_v1"
down_revision = "20291730_0090_cases_escalations"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

SUBSCRIPTION_STATUS = ["FREE", "ACTIVE", "PAUSED", "GRACE", "EXPIRED", "CANCELLED"]
MODULE_CODES = [
    "FUEL_CORE",
    "AI_ASSISTANT",
    "EXPLAIN",
    "PENALTIES",
    "MARKETPLACE",
    "ANALYTICS",
    "SLA",
    "BONUSES",
]


def _seed_free_plan(bind) -> None:
    schema_prefix = f"{SCHEMA}." if SCHEMA else ""
    plan_table = f"{schema_prefix}subscription_plans"
    modules_table = f"{schema_prefix}subscription_plan_modules"

    exists = bind.execute(sa.text(f"SELECT 1 FROM {plan_table} WHERE code = :code"), {"code": "FREE"}).first()
    if exists:
        return

    now = datetime.now(timezone.utc)
    plan_id = str(uuid.uuid4())
    bind.execute(
        sa.text(
            f"""
            INSERT INTO {plan_table} (id, code, title, description, is_active, billing_period_months, price_cents, currency, created_at, updated_at)
            VALUES (:id, :code, :title, :description, :is_active, :billing_period_months, :price_cents, :currency, :created_at, :updated_at)
            """
        ),
        {
            "id": plan_id,
            "code": "FREE",
            "title": "FREE",
            "description": "Базовая бесплатная подписка",
            "is_active": True,
            "billing_period_months": 0,
            "price_cents": 0,
            "currency": "RUB",
            "created_at": now,
            "updated_at": now,
        },
    )

    base_modules = {
        "FUEL_CORE": {"enabled": True, "tier": "free", "limits": {"cards_max": 5}},
        "MARKETPLACE": {"enabled": True, "tier": "free", "limits": {"discounts": False}},
        "EXPLAIN": {"enabled": True, "tier": "free", "limits": {"depth": 1}},
    }

    for module_code in MODULE_CODES:
        config = base_modules.get(module_code, {"enabled": False, "tier": "free", "limits": {}})
        bind.execute(
            sa.text(
                f"""
                INSERT INTO {modules_table} (plan_id, module_code, enabled, tier, limits, created_at, updated_at)
                VALUES (:plan_id, :module_code, :enabled, :tier, :limits, :created_at, :updated_at)
                """
            ),
            {
                "plan_id": plan_id,
                "module_code": module_code,
                "enabled": config["enabled"],
                "tier": config["tier"],
                "created_at": now,
                "updated_at": now,
                "limits": json.dumps(config["limits"]),
            },
        )


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "subscription_status", SUBSCRIPTION_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "subscription_module_code", MODULE_CODES, schema=SCHEMA)

    status_enum = safe_enum(bind, "subscription_status", SUBSCRIPTION_STATUS, schema=SCHEMA)
    module_enum = safe_enum(bind, "subscription_module_code", MODULE_CODES, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "subscription_plans",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("billing_period_months", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("price_cents", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'RUB'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(bind, "uq_subscription_plans_code", "subscription_plans", ["code"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "subscription_plan_modules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("module_code", module_enum, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tier", sa.String(length=32), nullable=True),
        sa.Column("limits", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], [f"{SCHEMA}.subscription_plans.id" if SCHEMA else "subscription_plans.id"]),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_subscription_plan_modules_plan_module",
        "subscription_plan_modules",
        ["plan_id", "module_code"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "client_subscriptions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], [f"{SCHEMA}.subscription_plans.id" if SCHEMA else "subscription_plans.id"]),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_client_subscriptions_tenant_client_status",
        "client_subscriptions",
        ["tenant_id", "client_id", "status"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "role_entitlements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("role_code", sa.String(length=64), nullable=False),
        sa.Column("entitlements", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], [f"{SCHEMA}.subscription_plans.id" if SCHEMA else "subscription_plans.id"]),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_role_entitlements_plan_role",
        "role_entitlements",
        ["plan_id", "role_code"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "bonus_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.String(length=64), nullable=True),
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=True),
        sa.Column("reward", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], [f"{SCHEMA}.subscription_plans.id" if SCHEMA else "subscription_plans.id"]),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_bonus_rules_plan", "bonus_rules", ["plan_id"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "client_bonus_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("active_bonuses", sa.JSON(), nullable=True),
        sa.Column("streaks", sa.JSON(), nullable=True),
        sa.Column("achievements", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_client_bonus_state_tenant_client", "client_bonus_state", ["tenant_id", "client_id"], schema=SCHEMA)

    _seed_free_plan(bind)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
