"""Seed subscription packages v1.

Revision ID: 20291760_0093_seed_subscription_packages_v1
Revises: 20291750_0092_gamification_v1
Create Date: 2025-03-06 00:00:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

import sqlalchemy as sa
from alembic import op

from app.alembic.helpers import column_exists, table_exists
from app.db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20291760_0093_seed_subscription_packages_v1"
down_revision = "20291750_0092_gamification_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: object | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _schema_prefix() -> str:
    return f"{SCHEMA}." if SCHEMA else ""


def _upsert_plan(bind, plan: dict) -> str:
    schema_prefix = _schema_prefix()
    plan_table = f"{schema_prefix}subscription_plans"
    now = _now()

    existing = bind.execute(sa.text(f"SELECT id FROM {plan_table} WHERE code = :code"), {"code": plan["code"]}).first()
    if existing:
        plan_id = existing[0]
        bind.execute(
            sa.text(
                f"""
                UPDATE {plan_table}
                SET title = :title,
                    description = :description,
                    is_active = :is_active,
                    billing_period_months = :billing_period_months,
                    price_cents = :price_cents,
                    discount_percent = :discount_percent,
                    bonus_multiplier_override = :bonus_multiplier_override,
                    currency = :currency,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {
                "id": plan_id,
                "title": plan["title"],
                "description": plan.get("description"),
                "is_active": plan.get("is_active", True),
                "billing_period_months": plan.get("billing_period_months", 0),
                "price_cents": plan.get("price_cents", 0),
                "discount_percent": plan.get("discount_percent", 0),
                "bonus_multiplier_override": plan.get("bonus_multiplier_override"),
                "currency": plan.get("currency", "RUB"),
                "updated_at": now,
            },
        )
        return plan_id

    plan_id = str(uuid.uuid4())
    bind.execute(
        sa.text(
            f"""
            INSERT INTO {plan_table}
                (id, code, title, description, is_active, billing_period_months, price_cents,
                 discount_percent, bonus_multiplier_override, currency, created_at, updated_at)
            VALUES
                (:id, :code, :title, :description, :is_active, :billing_period_months, :price_cents,
                 :discount_percent, :bonus_multiplier_override, :currency, :created_at, :updated_at)
            """
        ),
        {
            "id": plan_id,
            "code": plan["code"],
            "title": plan["title"],
            "description": plan.get("description"),
            "is_active": plan.get("is_active", True),
            "billing_period_months": plan.get("billing_period_months", 0),
            "price_cents": plan.get("price_cents", 0),
            "discount_percent": plan.get("discount_percent", 0),
            "bonus_multiplier_override": plan.get("bonus_multiplier_override"),
            "currency": plan.get("currency", "RUB"),
            "created_at": now,
            "updated_at": now,
        },
    )
    return plan_id


def _upsert_module(bind, *, plan_id: str, module_code: str, config: dict) -> None:
    schema_prefix = _schema_prefix()
    modules_table = f"{schema_prefix}subscription_plan_modules"
    now = _now()

    existing = bind.execute(
        sa.text(
            f"SELECT id FROM {modules_table} WHERE plan_id = :plan_id AND module_code = :module_code"
        ),
        {"plan_id": plan_id, "module_code": module_code},
    ).first()

    payload = {
        "plan_id": plan_id,
        "module_code": module_code,
        "enabled": config.get("enabled", False),
        "tier": config.get("tier"),
        "limits": _json(config.get("limits")),
        "updated_at": now,
    }

    if existing:
        bind.execute(
            sa.text(
                f"""
                UPDATE {modules_table}
                SET enabled = :enabled,
                    tier = :tier,
                    limits = :limits,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {**payload, "id": existing[0]},
        )
        return

    bind.execute(
        sa.text(
            f"""
            INSERT INTO {modules_table}
                (plan_id, module_code, enabled, tier, limits, created_at, updated_at)
            VALUES
                (:plan_id, :module_code, :enabled, :tier, :limits, :created_at, :updated_at)
            """
        ),
        {**payload, "created_at": now},
    )


def _upsert_role_entitlement(bind, *, plan_id: str, role_code: str, entitlements: dict) -> None:
    schema_prefix = _schema_prefix()
    table = f"{schema_prefix}role_entitlements"
    now = _now()

    existing = bind.execute(
        sa.text(f"SELECT id FROM {table} WHERE plan_id = :plan_id AND role_code = :role_code"),
        {"plan_id": plan_id, "role_code": role_code},
    ).first()

    payload = {
        "plan_id": plan_id,
        "role_code": role_code,
        "entitlements": _json(entitlements),
        "updated_at": now,
    }

    if existing:
        bind.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET entitlements = :entitlements,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {**payload, "id": existing[0]},
        )
        return

    bind.execute(
        sa.text(
            f"""
            INSERT INTO {table}
                (plan_id, role_code, entitlements, created_at, updated_at)
            VALUES
                (:plan_id, :role_code, :entitlements, :created_at, :updated_at)
            """
        ),
        {**payload, "created_at": now},
    )


def _upsert_bonus_rule(bind, *, plan_id: str, rule_code: str, title: str, reward: dict) -> None:
    schema_prefix = _schema_prefix()
    table = f"{schema_prefix}bonus_rules"
    now = _now()

    existing = bind.execute(
        sa.text(f"SELECT id FROM {table} WHERE plan_id = :plan_id AND rule_code = :rule_code"),
        {"plan_id": plan_id, "rule_code": rule_code},
    ).first()

    payload = {
        "plan_id": plan_id,
        "rule_code": rule_code,
        "title": title,
        "condition": None,
        "reward": _json(reward),
        "enabled": True,
        "updated_at": now,
    }

    if existing:
        bind.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET title = :title,
                    condition = :condition,
                    reward = :reward,
                    enabled = :enabled,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {**payload, "id": existing[0]},
        )
        return

    bind.execute(
        sa.text(
            f"""
            INSERT INTO {table}
                (plan_id, rule_code, title, condition, reward, enabled, created_at, updated_at)
            VALUES
                (:plan_id, :rule_code, :title, :condition, :reward, :enabled, :created_at, :updated_at)
            """
        ),
        {**payload, "created_at": now},
    )


def _upsert_achievement(bind, *, code: str, title: str, description: str, plan_codes: list[str]) -> None:
    schema_prefix = _schema_prefix()
    table = f"{schema_prefix}achievements"
    now = _now()

    existing = bind.execute(sa.text(f"SELECT id FROM {table} WHERE code = :code"), {"code": code}).first()
    payload = {
        "code": code,
        "title": title,
        "description": description,
        "is_active": True,
        "is_hidden": False,
        "module_code": None,
        "plan_codes": _json(plan_codes),
        "updated_at": now,
    }

    if existing:
        bind.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET title = :title,
                    description = :description,
                    is_active = :is_active,
                    is_hidden = :is_hidden,
                    module_code = :module_code,
                    plan_codes = :plan_codes,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {**payload, "id": existing[0]},
        )
        return

    bind.execute(
        sa.text(
            f"""
            INSERT INTO {table}
                (code, title, description, is_active, is_hidden, module_code, plan_codes, created_at, updated_at)
            VALUES
                (:code, :title, :description, :is_active, :is_hidden, :module_code, :plan_codes, :created_at, :updated_at)
            """
        ),
        {**payload, "created_at": now},
    )


def _upsert_streak(bind, *, code: str, title: str, description: str, plan_codes: list[str]) -> None:
    schema_prefix = _schema_prefix()
    table = f"{schema_prefix}streaks"
    now = _now()

    existing = bind.execute(sa.text(f"SELECT id FROM {table} WHERE code = :code"), {"code": code}).first()
    payload = {
        "code": code,
        "title": title,
        "description": description,
        "is_active": True,
        "module_code": None,
        "plan_codes": _json(plan_codes),
        "condition": None,
        "updated_at": now,
    }

    if existing:
        bind.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET title = :title,
                    description = :description,
                    is_active = :is_active,
                    module_code = :module_code,
                    plan_codes = :plan_codes,
                    condition = :condition,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {**payload, "id": existing[0]},
        )
        return

    bind.execute(
        sa.text(
            f"""
            INSERT INTO {table}
                (code, title, description, is_active, module_code, plan_codes, condition, created_at, updated_at)
            VALUES
                (:code, :title, :description, :is_active, :module_code, :plan_codes, :condition, :created_at, :updated_at)
            """
        ),
        {**payload, "created_at": now},
    )


def _upsert_bonus(bind, *, code: str, title: str, description: str, reward: dict, plan_codes: list[str]) -> None:
    schema_prefix = _schema_prefix()
    table = f"{schema_prefix}bonuses"
    now = _now()

    existing = bind.execute(sa.text(f"SELECT id FROM {table} WHERE code = :code"), {"code": code}).first()
    payload = {
        "code": code,
        "title": title,
        "description": description,
        "reward": _json(reward),
        "is_active": True,
        "plan_codes": _json(plan_codes),
        "updated_at": now,
    }

    if existing:
        bind.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET title = :title,
                    description = :description,
                    reward = :reward,
                    is_active = :is_active,
                    plan_codes = :plan_codes,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {**payload, "id": existing[0]},
        )
        return

    bind.execute(
        sa.text(
            f"""
            INSERT INTO {table}
                (code, title, description, reward, is_active, plan_codes, created_at, updated_at)
            VALUES
                (:code, :title, :description, :reward, :is_active, :plan_codes, :created_at, :updated_at)
            """
        ),
        {**payload, "created_at": now},
    )


def _full_module_set(config: dict) -> dict[str, dict]:
    full = {}
    for code in MODULE_CODES:
        full[code] = config.get(code, {"enabled": False, "tier": "off", "limits": {}})
    return full


def _seed_plans(bind) -> None:
    if not table_exists(bind, "subscription_plans", schema=SCHEMA):
        return

    free_cards = {
        "INDIVIDUAL": 1,
        "SELF_EMPLOYED": 3,
        "SMB_FLEET": 20,
        "ENTERPRISE": 100,
    }

    role_entitlements = [
        {"role_code": "OWNER", "entitlements": {"scope": "all"}},
        {"role_code": "MANAGER", "entitlements": {"scope": "all", "restricted": ["plan_change"]}},
        {
            "role_code": "ACCOUNTANT",
            "entitlements": {"scope": "limited", "permissions": ["invoices", "exports", "penalties"]},
        },
        {"role_code": "DRIVER", "entitlements": {"scope": "limited", "permissions": ["operations", "limits"]}},
        {
            "role_code": "ANALYST",
            "entitlements": {"scope": "read_only", "permissions": ["analytics", "explain"]},
        },
    ]

    plans: list[dict] = []
    control_plan_codes: list[str] = []
    optimize_plan_codes: list[str] = []
    enterprise_plan_codes: list[str] = []

    def add_plan(plan: dict) -> None:
        plans.append(plan)
        code = plan["code"]
        if code.startswith("CONTROL_"):
            control_plan_codes.append(code)
        if code.startswith("OPTIMIZE_"):
            optimize_plan_codes.append(code)
        if code.startswith("ENTERPRISE_"):
            enterprise_plan_codes.append(code)

    free_modules = _full_module_set(
        {
            "FUEL_CORE": {"enabled": True, "tier": "free", "limits": {"cards_max": free_cards}},
            "MARKETPLACE": {
                "enabled": True,
                "tier": "free",
                "limits": {"marketplace_discount_percent": 0},
            },
            "EXPLAIN": {
                "enabled": True,
                "tier": "basic",
                "limits": {"explain_depth": 1, "explain_diff": False, "what_if": "off"},
            },
            "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"exports_per_month": 1}},
            "BONUSES": {
                "enabled": True,
                "tier": "preview",
                "limits": {"preview_only": True, "bonus_multiplier": 0},
            },
        }
    )

    add_plan(
        {
            "code": "FREE_BASE",
            "title": "FREE",
            "description": "Бесплатный пакет для всех сегментов клиентов.",
            "billing_period_months": 0,
            "price_cents": 0,
            "discount_percent": 0,
            "bonus_multiplier_override": None,
            "modules": free_modules,
        }
    )

    def _bonus_override(base: float, boost: float) -> float:
        return round(base + boost, 2)

    def _control_modules(
        cards_max: int, bonus_multiplier: float, bonus_override: float | None, bonus_boost: float
    ) -> dict:
        limits = {"bonus_multiplier": bonus_multiplier}
        if bonus_override is not None:
            limits["bonus_multiplier_override"] = bonus_override
            limits["bonus_level_boost"] = bonus_boost
        return _full_module_set(
            {
                "FUEL_CORE": {"enabled": True, "tier": "control", "limits": {"cards_max": cards_max}},
                "ANALYTICS": {
                    "enabled": True,
                    "tier": "standard",
                    "limits": {"exports_per_month": 10, "kpi_reports": True},
                },
                "EXPLAIN": {
                    "enabled": True,
                    "tier": "standard",
                    "limits": {"explain_depth": 2, "explain_diff": False, "what_if": "off"},
                },
                "PENALTIES": {
                    "enabled": True,
                    "tier": "monitoring",
                    "limits": {"penalties_mode": "monitoring"},
                },
                "MARKETPLACE": {
                    "enabled": True,
                    "tier": "basic",
                    "limits": {"marketplace_discount_percent": 2},
                },
                "BONUSES": {"enabled": True, "tier": "standard", "limits": limits},
                "SLA": {
                    "enabled": True,
                    "tier": "basic",
                    "limits": {"sla_first_response_minutes": 240, "sla_resolve_minutes": 2880},
                },
                "AI_ASSISTANT": {"enabled": True, "tier": "lite", "limits": {"ai_tier": "lite"}},
            }
        )

    def _optimize_modules(
        cards_max: int, bonus_multiplier: float, bonus_override: float | None, bonus_boost: float
    ) -> dict:
        limits = {"bonus_multiplier": bonus_multiplier}
        if bonus_override is not None:
            limits["bonus_multiplier_override"] = bonus_override
            limits["bonus_level_boost"] = bonus_boost
        return _full_module_set(
            {
                "FUEL_CORE": {"enabled": True, "tier": "optimize", "limits": {"cards_max": cards_max}},
                "ANALYTICS": {
                    "enabled": True,
                    "tier": "pro",
                    "limits": {"exports_per_month": 50, "economy_insights": True, "trend_reports": True},
                },
                "EXPLAIN": {
                    "enabled": True,
                    "tier": "full",
                    "limits": {"explain_depth": 3, "explain_diff": True, "what_if": "read_only"},
                },
                "PENALTIES": {
                    "enabled": True,
                    "tier": "assist",
                    "limits": {"penalties_mode": "assist"},
                },
                "MARKETPLACE": {
                    "enabled": True,
                    "tier": "pro",
                    "limits": {"marketplace_discount_percent": 5},
                },
                "BONUSES": {"enabled": True, "tier": "pro", "limits": limits},
                "SLA": {
                    "enabled": True,
                    "tier": "full",
                    "limits": {"sla_first_response_minutes": 60, "sla_resolve_minutes": 1440},
                },
                "AI_ASSISTANT": {"enabled": True, "tier": "pro", "limits": {"ai_tier": "pro"}},
            }
        )

    def _enterprise_modules(cards_max: int, bonus_multiplier: float) -> dict:
        return _full_module_set(
            {
                "FUEL_CORE": {"enabled": True, "tier": "enterprise", "limits": {"cards_max": cards_max}},
                "ANALYTICS": {
                    "enabled": True,
                    "tier": "enterprise",
                    "limits": {"exports_per_month": 200, "economy_insights": True, "trend_reports": True},
                },
                "EXPLAIN": {
                    "enabled": True,
                    "tier": "full",
                    "limits": {"explain_depth": 3, "explain_diff": True, "what_if": "read_only"},
                },
                "PENALTIES": {
                    "enabled": True,
                    "tier": "auto",
                    "limits": {"penalties_mode": "auto"},
                },
                "MARKETPLACE": {
                    "enabled": True,
                    "tier": "enterprise",
                    "limits": {"marketplace_discount_percent": 10},
                },
                "BONUSES": {"enabled": True, "tier": "enterprise", "limits": {"bonus_multiplier": bonus_multiplier}},
                "SLA": {
                    "enabled": True,
                    "tier": "strict",
                    "limits": {"sla_first_response_minutes": 30, "sla_resolve_minutes": 720},
                },
                "AI_ASSISTANT": {"enabled": True, "tier": "pro", "limits": {"ai_tier": "pro"}},
            }
        )

    def _partner_modules(config: dict) -> dict:
        return _full_module_set(config)

    def _variant_price(base_price: int, discount_percent: int) -> int:
        return int(round(base_price * (1 - discount_percent / 100)))

    segments = {
        "INDIVIDUAL": {
            "segment": "INDIVIDUAL",
            "cards_control": 5,
            "cards_optimize": 10,
            "control_price": 9900,
            "optimize_price": 19900,
        },
        "SELF_EMPLOYED": {
            "segment": "SELF_EMPLOYED",
            "cards_control": 10,
            "cards_optimize": 20,
            "control_price": 14900,
            "optimize_price": 24900,
        },
        "SMB_FLEET": {
            "segment": "SMB_FLEET",
            "cards_control": 50,
            "cards_optimize": 100,
            "control_price": 29900,
            "optimize_price": 49900,
        },
        "ENTERPRISE": {
            "segment": "ENTERPRISE",
            "cards_control": 200,
            "cards_optimize": 500,
            "control_price": 69900,
            "optimize_price": 99900,
        },
    }

    control_bonus = 1.0
    optimize_bonus = 1.5
    enterprise_bonus = 2.0

    for segment_code, segment in segments.items():
        base_code = f"CONTROL_{segment_code}"
        for months, discount, bonus_boost in [(1, 0, 0.0), (6, 10, 0.1), (12, 20, 0.2)]:
            bonus_override = _bonus_override(control_bonus, bonus_boost) if bonus_boost else None
            add_plan(
                {
                    "code": f"{base_code}_{months}M",
                    "title": f"CONTROL {segment['segment']} {months}M",
                    "description": f"CONTROL для сегмента {segment['segment']}, {months} мес.",
                    "billing_period_months": months,
                    "price_cents": _variant_price(segment["control_price"], discount),
                    "discount_percent": discount,
                    "bonus_multiplier_override": bonus_override,
                    "modules": _control_modules(segment["cards_control"], control_bonus, bonus_override, bonus_boost),
                }
            )

    for segment_code, segment in segments.items():
        base_code = f"OPTIMIZE_{segment_code}"
        for months, discount, bonus_boost in [(1, 0, 0.0), (6, 10, 0.1), (12, 20, 0.2)]:
            bonus_override = _bonus_override(optimize_bonus, bonus_boost) if bonus_boost else None
            add_plan(
                {
                    "code": f"{base_code}_{months}M",
                    "title": f"OPTIMIZE {segment['segment']} {months}M",
                    "description": f"OPTIMIZE для сегмента {segment['segment']}, {months} мес.",
                    "billing_period_months": months,
                    "price_cents": _variant_price(segment["optimize_price"], discount),
                    "discount_percent": discount,
                    "bonus_multiplier_override": bonus_override,
                    "modules": _optimize_modules(segment["cards_optimize"], optimize_bonus, bonus_override, bonus_boost),
                }
            )

    add_plan(
        {
            "code": "ENTERPRISE_CUSTOM",
            "title": "ENTERPRISE",
            "description": "Контрактный пакет для enterprise с индивидуальными условиями.",
            "billing_period_months": 0,
            "price_cents": 0,
            "discount_percent": 0,
            "bonus_multiplier_override": None,
            "modules": _enterprise_modules("custom", enterprise_bonus),
        }
    )

    partner_plans = [
        {
            "code": "PARTNER_MKT_FREE",
            "title": "Marketplace Provider Free",
            "description": "Партнерский пакет для marketplace provider (free).",
            "billing_period_months": 0,
            "price_cents": 0,
            "discount_percent": 0,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "free",
                        "limits": {"commission_percent": 10, "api_rate_limit_per_min": 60},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"orders_analytics": True}},
                }
            ),
        },
        {
            "code": "PARTNER_MKT_PRO_1M",
            "title": "Marketplace Provider Pro 1M",
            "description": "Партнерский пакет для marketplace provider (pro, 1 мес).",
            "billing_period_months": 1,
            "price_cents": 19900,
            "discount_percent": 0,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "pro",
                        "limits": {"commission_percent": 5, "api_rate_limit_per_min": 300},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "basic", "limits": {"sla_first_response_minutes": 240}},
                }
            ),
        },
        {
            "code": "PARTNER_MKT_PRO_6M",
            "title": "Marketplace Provider Pro 6M",
            "description": "Партнерский пакет для marketplace provider (pro, 6 мес).",
            "billing_period_months": 6,
            "price_cents": _variant_price(19900, 10),
            "discount_percent": 10,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "pro",
                        "limits": {"commission_percent": 5, "api_rate_limit_per_min": 300},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "basic", "limits": {"sla_first_response_minutes": 240}},
                }
            ),
        },
        {
            "code": "PARTNER_MKT_PRO_12M",
            "title": "Marketplace Provider Pro 12M",
            "description": "Партнерский пакет для marketplace provider (pro, 12 мес).",
            "billing_period_months": 12,
            "price_cents": _variant_price(19900, 20),
            "discount_percent": 20,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "pro",
                        "limits": {"commission_percent": 5, "api_rate_limit_per_min": 300},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "basic", "limits": {"sla_first_response_minutes": 240}},
                }
            ),
        },
        {
            "code": "PARTNER_FUEL_BASIC_1M",
            "title": "Fuel Station Network Basic 1M",
            "description": "Партнерский пакет для сети АЗС (basic, 1 мес).",
            "billing_period_months": 1,
            "price_cents": 24900,
            "discount_percent": 0,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "FUEL_CORE": {
                        "enabled": True,
                        "tier": "basic",
                        "limits": {"stations_max": 5, "api_rate_limit_per_min": 60},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"orders_analytics": True}},
                }
            ),
        },
        {
            "code": "PARTNER_FUEL_BASIC_6M",
            "title": "Fuel Station Network Basic 6M",
            "description": "Партнерский пакет для сети АЗС (basic, 6 мес).",
            "billing_period_months": 6,
            "price_cents": _variant_price(24900, 10),
            "discount_percent": 10,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "FUEL_CORE": {
                        "enabled": True,
                        "tier": "basic",
                        "limits": {"stations_max": 5, "api_rate_limit_per_min": 60},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"orders_analytics": True}},
                }
            ),
        },
        {
            "code": "PARTNER_FUEL_BASIC_12M",
            "title": "Fuel Station Network Basic 12M",
            "description": "Партнерский пакет для сети АЗС (basic, 12 мес).",
            "billing_period_months": 12,
            "price_cents": _variant_price(24900, 20),
            "discount_percent": 20,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "FUEL_CORE": {
                        "enabled": True,
                        "tier": "basic",
                        "limits": {"stations_max": 5, "api_rate_limit_per_min": 60},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"orders_analytics": True}},
                }
            ),
        },
        {
            "code": "PARTNER_FUEL_ENTERPRISE_1M",
            "title": "Fuel Station Network Enterprise 1M",
            "description": "Партнерский пакет для сети АЗС (enterprise, 1 мес).",
            "billing_period_months": 1,
            "price_cents": 79900,
            "discount_percent": 0,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "FUEL_CORE": {
                        "enabled": True,
                        "tier": "enterprise",
                        "limits": {"stations_max": 50, "api_rate_limit_per_min": 300},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "strict", "limits": {"sla_first_response_minutes": 60}},
                }
            ),
        },
        {
            "code": "PARTNER_FUEL_ENTERPRISE_6M",
            "title": "Fuel Station Network Enterprise 6M",
            "description": "Партнерский пакет для сети АЗС (enterprise, 6 мес).",
            "billing_period_months": 6,
            "price_cents": _variant_price(79900, 10),
            "discount_percent": 10,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "FUEL_CORE": {
                        "enabled": True,
                        "tier": "enterprise",
                        "limits": {"stations_max": 50, "api_rate_limit_per_min": 300},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "strict", "limits": {"sla_first_response_minutes": 60}},
                }
            ),
        },
        {
            "code": "PARTNER_FUEL_ENTERPRISE_12M",
            "title": "Fuel Station Network Enterprise 12M",
            "description": "Партнерский пакет для сети АЗС (enterprise, 12 мес).",
            "billing_period_months": 12,
            "price_cents": _variant_price(79900, 20),
            "discount_percent": 20,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "FUEL_CORE": {
                        "enabled": True,
                        "tier": "enterprise",
                        "limits": {"stations_max": 50, "api_rate_limit_per_min": 300},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "strict", "limits": {"sla_first_response_minutes": 60}},
                }
            ),
        },
        {
            "code": "PARTNER_SERVICE_BASIC_1M",
            "title": "Service Center Basic 1M",
            "description": "Партнерский пакет для сервисных центров (basic, 1 мес).",
            "billing_period_months": 1,
            "price_cents": 14900,
            "discount_percent": 0,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "basic",
                        "limits": {"service_cards_max": 50, "api_rate_limit_per_min": 60},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"orders_analytics": True}},
                }
            ),
        },
        {
            "code": "PARTNER_SERVICE_BASIC_6M",
            "title": "Service Center Basic 6M",
            "description": "Партнерский пакет для сервисных центров (basic, 6 мес).",
            "billing_period_months": 6,
            "price_cents": _variant_price(14900, 10),
            "discount_percent": 10,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "basic",
                        "limits": {"service_cards_max": 50, "api_rate_limit_per_min": 60},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"orders_analytics": True}},
                }
            ),
        },
        {
            "code": "PARTNER_SERVICE_BASIC_12M",
            "title": "Service Center Basic 12M",
            "description": "Партнерский пакет для сервисных центров (basic, 12 мес).",
            "billing_period_months": 12,
            "price_cents": _variant_price(14900, 20),
            "discount_percent": 20,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "basic",
                        "limits": {"service_cards_max": 50, "api_rate_limit_per_min": 60},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"orders_analytics": True}},
                }
            ),
        },
        {
            "code": "PARTNER_SERVICE_PRO_1M",
            "title": "Service Center Pro 1M",
            "description": "Партнерский пакет для сервисных центров (pro, 1 мес).",
            "billing_period_months": 1,
            "price_cents": 29900,
            "discount_percent": 0,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "pro",
                        "limits": {"service_cards_max": 200, "api_rate_limit_per_min": 300},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "basic", "limits": {"sla_first_response_minutes": 240}},
                }
            ),
        },
        {
            "code": "PARTNER_SERVICE_PRO_6M",
            "title": "Service Center Pro 6M",
            "description": "Партнерский пакет для сервисных центров (pro, 6 мес).",
            "billing_period_months": 6,
            "price_cents": _variant_price(29900, 10),
            "discount_percent": 10,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "pro",
                        "limits": {"service_cards_max": 200, "api_rate_limit_per_min": 300},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "basic", "limits": {"sla_first_response_minutes": 240}},
                }
            ),
        },
        {
            "code": "PARTNER_SERVICE_PRO_12M",
            "title": "Service Center Pro 12M",
            "description": "Партнерский пакет для сервисных центров (pro, 12 мес).",
            "billing_period_months": 12,
            "price_cents": _variant_price(29900, 20),
            "discount_percent": 20,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "pro",
                        "limits": {"service_cards_max": 200, "api_rate_limit_per_min": 300},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "basic", "limits": {"sla_first_response_minutes": 240}},
                }
            ),
        },
        {
            "code": "PARTNER_INT_BASIC_1M",
            "title": "Integrator Basic 1M",
            "description": "Партнерский пакет для интеграторов (basic, 1 мес).",
            "billing_period_months": 1,
            "price_cents": 19900,
            "discount_percent": 0,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "basic",
                        "limits": {"api_rate_limit_per_min": 120, "webhooks_enabled": True, "api_keys_max": 2},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"orders_analytics": True}},
                }
            ),
        },
        {
            "code": "PARTNER_INT_BASIC_6M",
            "title": "Integrator Basic 6M",
            "description": "Партнерский пакет для интеграторов (basic, 6 мес).",
            "billing_period_months": 6,
            "price_cents": _variant_price(19900, 10),
            "discount_percent": 10,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "basic",
                        "limits": {"api_rate_limit_per_min": 120, "webhooks_enabled": True, "api_keys_max": 2},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"orders_analytics": True}},
                }
            ),
        },
        {
            "code": "PARTNER_INT_BASIC_12M",
            "title": "Integrator Basic 12M",
            "description": "Партнерский пакет для интеграторов (basic, 12 мес).",
            "billing_period_months": 12,
            "price_cents": _variant_price(19900, 20),
            "discount_percent": 20,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "basic",
                        "limits": {"api_rate_limit_per_min": 120, "webhooks_enabled": True, "api_keys_max": 2},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "basic", "limits": {"orders_analytics": True}},
                }
            ),
        },
        {
            "code": "PARTNER_INT_PRO_1M",
            "title": "Integrator Pro 1M",
            "description": "Партнерский пакет для интеграторов (pro, 1 мес).",
            "billing_period_months": 1,
            "price_cents": 39900,
            "discount_percent": 0,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "pro",
                        "limits": {"api_rate_limit_per_min": 300, "webhooks_enabled": True, "api_keys_max": 10},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "basic", "limits": {"sla_first_response_minutes": 240}},
                }
            ),
        },
        {
            "code": "PARTNER_INT_PRO_6M",
            "title": "Integrator Pro 6M",
            "description": "Партнерский пакет для интеграторов (pro, 6 мес).",
            "billing_period_months": 6,
            "price_cents": _variant_price(39900, 10),
            "discount_percent": 10,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "pro",
                        "limits": {"api_rate_limit_per_min": 300, "webhooks_enabled": True, "api_keys_max": 10},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "basic", "limits": {"sla_first_response_minutes": 240}},
                }
            ),
        },
        {
            "code": "PARTNER_INT_PRO_12M",
            "title": "Integrator Pro 12M",
            "description": "Партнерский пакет для интеграторов (pro, 12 мес).",
            "billing_period_months": 12,
            "price_cents": _variant_price(39900, 20),
            "discount_percent": 20,
            "bonus_multiplier_override": None,
            "modules": _partner_modules(
                {
                    "MARKETPLACE": {
                        "enabled": True,
                        "tier": "pro",
                        "limits": {"api_rate_limit_per_min": 300, "webhooks_enabled": True, "api_keys_max": 10},
                    },
                    "ANALYTICS": {"enabled": True, "tier": "pro", "limits": {"orders_analytics": True}},
                    "SLA": {"enabled": True, "tier": "basic", "limits": {"sla_first_response_minutes": 240}},
                }
            ),
        },
    ]

    for plan in partner_plans:
        add_plan(plan)

    paid_plan_codes = sorted(set(control_plan_codes + optimize_plan_codes + enterprise_plan_codes))
    optimize_plus_codes = sorted(set(optimize_plan_codes + enterprise_plan_codes))

    for plan in plans:
        plan_id = _upsert_plan(bind, plan)
        for module_code, config in plan.get("modules", {}).items():
            _upsert_module(bind, plan_id=plan_id, module_code=module_code, config=config)
        for role in role_entitlements:
            _upsert_role_entitlement(
                bind,
                plan_id=plan_id,
                role_code=role["role_code"],
                entitlements=role["entitlements"],
            )

        bonus_multiplier = plan.get("modules", {}).get("BONUSES", {}).get("limits", {}).get("bonus_multiplier")
        if bonus_multiplier:
            bonus_override = plan.get("bonus_multiplier_override") or bonus_multiplier
            _upsert_bonus_rule(
                bind,
                plan_id=plan_id,
                rule_code=f"BONUS_MULTIPLIER_{plan['code']}",
                title="Bonus multiplier",
                reward={"bonus_multiplier": bonus_override},
            )

    _upsert_achievement(
        bind,
        code="ACH_NO_PENALTIES_30D",
        title="30 дней без штрафов",
        description="Нет штрафов в течение 30 дней.",
        plan_codes=optimize_plus_codes,
    )
    _upsert_achievement(
        bind,
        code="ACH_EXPORTS_ONTIME_7D",
        title="Экспорты вовремя",
        description="Все экспорты выполнены вовремя 7 дней подряд.",
        plan_codes=paid_plan_codes,
    )
    _upsert_achievement(
        bind,
        code="ACH_DECLINES_DOWN_14D",
        title="Снижение отказов",
        description="Снижение отказов на протяжении 14 дней.",
        plan_codes=optimize_plus_codes,
    )
    _upsert_achievement(
        bind,
        code="ACH_FUEL_PARTNER_USAGE_10",
        title="10 операций у партнера",
        description="10 операций у топливного партнера.",
        plan_codes=paid_plan_codes,
    )
    _upsert_achievement(
        bind,
        code="ACH_STABLE_PAYMENTS_3M",
        title="Стабильные платежи 3 месяца",
        description="Платежи стабильны в течение 3 месяцев.",
        plan_codes=optimize_plus_codes,
    )

    _upsert_streak(
        bind,
        code="STREAK_NO_CRITICAL_ERRORS_7D",
        title="7 дней без критических ошибок",
        description="Серия без критических ошибок 7 дней подряд.",
        plan_codes=paid_plan_codes,
    )
    _upsert_streak(
        bind,
        code="STREAK_DISCIPLINE_PAYMENTS_30D",
        title="Дисциплина платежей 30 дней",
        description="Платежи дисциплинированно 30 дней подряд.",
        plan_codes=paid_plan_codes,
    )

    _upsert_bonus(
        bind,
        code="BONUS_MARKETPLACE_DISCOUNT",
        title="Скидка в маркетплейсе",
        description="Дополнительная скидка на предложения маркетплейса.",
        reward={"discount_percent_on_marketplace": 5},
        plan_codes=paid_plan_codes,
    )
    _upsert_bonus(
        bind,
        code="BONUS_FREE_EXPORTS",
        title="Бесплатные экспорты",
        description="Дополнительные бесплатные экспорты.",
        reward={"free_export_count": 5},
        plan_codes=paid_plan_codes,
    )
    _upsert_bonus(
        bind,
        code="BONUS_PRIORITY_SUPPORT",
        title="Приоритетная поддержка",
        description="Повышенный приоритет поддержки.",
        reward={"priority_support_level": "high"},
        plan_codes=paid_plan_codes,
    )
    _upsert_bonus(
        bind,
        code="BONUS_FUEL_CASHBACK",
        title="Кэшбэк на топливо",
        description="Кэшбэк на топливо для активных клиентов.",
        reward={"fuel_cashback_percent": 2},
        plan_codes=paid_plan_codes,
    )


def upgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "subscription_plans", schema=SCHEMA):
        if not column_exists(bind, "subscription_plans", "discount_percent", schema=SCHEMA):
            op.add_column(
                "subscription_plans",
                sa.Column("discount_percent", sa.Integer(), nullable=False, server_default=sa.text("0")),
                schema=SCHEMA,
            )
        if not column_exists(bind, "subscription_plans", "bonus_multiplier_override", schema=SCHEMA):
            op.add_column(
                "subscription_plans",
                sa.Column("bonus_multiplier_override", sa.Float(), nullable=True),
                schema=SCHEMA,
            )

    _seed_plans(bind)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
