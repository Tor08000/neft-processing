from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import MetaData, String, Table, cast, insert, inspect, select
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA


AVAILABILITY_ADDON = "ADDON_ELIGIBLE"
AVAILABILITY_DISABLED = "DISABLED"
AVAILABILITY_ENABLED = "ENABLED"

ADDON_FEATURE_MAP: dict[str, set[str]] = {
    "integration.helpdesk.zendesk": {
        "integration.helpdesk.outbound",
        "integration.helpdesk.inbound",
    },
    "integration.erp.accounting": {"integration.erp.accounting"},
    "integration.api.webhooks": {"integration.api.webhooks"},
    "feature.export.priority": {"feature.export.streaming_priority"},
}

LEGACY_MODULE_FEATURE_MAP: dict[str, set[str]] = {
    "FUEL_CORE": {"feature.portal.core", "feature.portal.entities"},
    "ANALYTICS": {
        "feature.portal.analytics",
        "feature.analytics",
        "feature.analytics.drill",
        "feature.export.async",
        "feature.export.xlsx",
        "feature.reports.xlsx",
    },
    "BILLING": {
        "feature.portal.billing",
        "feature.billing.invoices",
        "feature.export.async",
        "feature.export.xlsx",
        "feature.reports.xlsx",
    },
    "DOCS": {"feature.portal.billing", "feature.billing.invoices"},
    "MARKETPLACE": {"feature.marketplace", "feature.portal.marketplace"},
    "CRM": {"feature.portal.entities"},
    "SLA": {"support.priority", "support.incident_escalation", "slo.tiers"},
}

CAPABILITY_CLIENT_CORE = "CLIENT_CORE"
CAPABILITY_CLIENT_BILLING = "CLIENT_BILLING"
CAPABILITY_CLIENT_ANALYTICS = "CLIENT_ANALYTICS"
CAPABILITY_PARTNER_CORE = "PARTNER_CORE"
CAPABILITY_PARTNER_PRICING = "PARTNER_PRICING"
CAPABILITY_PARTNER_CATALOG = "PARTNER_CATALOG"
CAPABILITY_PARTNER_ORDERS = "PARTNER_ORDERS"
CAPABILITY_PARTNER_ANALYTICS = "PARTNER_ANALYTICS"
CAPABILITY_PARTNER_SETTLEMENTS = "PARTNER_SETTLEMENTS"
CAPABILITY_PARTNER_FINANCE_VIEW = "PARTNER_FINANCE_VIEW"
CAPABILITY_PARTNER_PAYOUT_REQUEST = "PARTNER_PAYOUT_REQUEST"
CAPABILITY_PARTNER_PAYOUT_APPROVAL = "PARTNER_PAYOUT_APPROVAL"
CAPABILITY_PARTNER_DOCUMENTS_LIST = "PARTNER_DOCUMENTS_LIST"
CAPABILITY_MARKETPLACE = "MARKETPLACE"
CAPABILITY_LOGISTICS = "LOGISTICS"

CLIENT_ROLE = "CLIENT"
PARTNER_ROLE = "PARTNER"


@dataclass(frozen=True)
class EntitlementsSnapshot:
    entitlements: dict[str, Any]
    hash: str
    computed_at: datetime
    subscription_id: int | None


def _bind(db: Session):
    try:
        return db.connection()
    except Exception:
        return db.get_bind()


def _table(db: Session, name: str) -> Table:
    bind = _bind(db)
    try:
        return Table(name, MetaData(), autoload_with=bind, schema=DB_SCHEMA)
    except Exception:
        if bind.dialect.name == "postgresql":
            raise
        return Table(name, MetaData(), autoload_with=bind)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tables_ready(db: Session, table_names: list[str]) -> bool:
    try:
        bind = _bind(db)
        inspector = inspect(bind)
        if bind.dialect.name != "postgresql":
            return all(
                inspector.has_table(name, schema=DB_SCHEMA) or inspector.has_table(name)
                for name in table_names
            )
        return all(inspector.has_table(name, schema=DB_SCHEMA) for name in table_names)
    except Exception:
        return False


def _table_exists(db: Session, name: str) -> bool:
    try:
        bind = _bind(db)
        inspector = inspect(bind)
        if inspector.has_table(name, schema=DB_SCHEMA):
            return True
        if bind.dialect.name != "postgresql":
            return inspector.has_table(name)
        return False
    except Exception:
        return False


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _reverse_addon_map() -> dict[str, set[str]]:
    feature_to_addons: dict[str, set[str]] = {}
    for addon_code, feature_keys in ADDON_FEATURE_MAP.items():
        for feature_key in feature_keys:
            feature_to_addons.setdefault(feature_key, set()).add(addon_code)
    return feature_to_addons


def _normalize_subscription_status(status: str | None) -> str | None:
    if not status:
        return None
    upper = str(status).upper()
    if upper in {"PAST_DUE", "OVERDUE"}:
        return "OVERDUE"
    if upper == "SUSPENDED":
        return "SUSPENDED"
    if upper == "ACTIVE":
        return "ACTIVE"
    return upper


def _feature_available(availability: str | None) -> bool:
    return availability in {AVAILABILITY_ENABLED, "LIMITED"}


def _has_feature(features: dict[str, dict[str, Any]], feature_keys: list[str] | None) -> bool:
    if not feature_keys:
        return True
    if not features:
        return True
    return any(_feature_available((features.get(key) or {}).get("availability")) for key in feature_keys)


def _has_module(modules: dict[str, dict[str, Any]], module_codes: list[str] | None) -> bool:
    if not module_codes:
        return True
    if not modules:
        return True
    return any((modules.get(code) or {}).get("enabled") for code in module_codes)


def _entitlement_allows(
    features: dict[str, dict[str, Any]],
    modules: dict[str, dict[str, Any]],
    feature_keys: list[str] | None,
    module_codes: list[str] | None,
) -> bool:
    feature_ok = _has_feature(features, feature_keys)
    module_ok = _has_module(modules, module_codes)
    if feature_keys and module_codes:
        return feature_ok or module_ok
    return feature_ok and module_ok


def _load_org_roles(db: Session, *, org_id: int) -> list[str]:
    if not _table_exists(db, "orgs"):
        return []
    orgs = _table(db, "orgs")
    if "roles" not in orgs.c:
        return []
    record = db.execute(select(orgs.c.roles).where(orgs.c.id == org_id)).mappings().first()
    if not record:
        return []
    roles = record.get("roles")
    if not roles:
        return []
    if isinstance(roles, str):
        roles = [roles]
    return sorted({str(role).upper() for role in roles if role})


def _compute_capabilities(
    *,
    org_roles: list[str],
    features: dict[str, dict[str, Any]],
    modules: dict[str, dict[str, Any]],
    subscription_status: str | None,
) -> list[str]:
    billing_blocked = subscription_status in {"OVERDUE", "SUSPENDED"}

    rules = [
        {
            "code": CAPABILITY_CLIENT_CORE,
            "roles": {CLIENT_ROLE},
            "feature_keys": ["feature.portal.core", "feature.portal.entities"],
            "module_codes": None,
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_CLIENT_BILLING,
            "roles": {CLIENT_ROLE},
            "feature_keys": ["feature.portal.billing", "feature.billing.invoices"],
            "module_codes": ["BILLING", "DOCS"],
            "billing_scoped": True,
        },
        {
            "code": CAPABILITY_CLIENT_ANALYTICS,
            "roles": {CLIENT_ROLE},
            "feature_keys": ["feature.portal.analytics", "feature.analytics"],
            "module_codes": ["ANALYTICS"],
            "billing_scoped": True,
        },
        {
            "code": CAPABILITY_PARTNER_CORE,
            "roles": {PARTNER_ROLE},
            "feature_keys": ["feature.partner.core"],
            "module_codes": None,
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_PARTNER_PRICING,
            "roles": {PARTNER_ROLE},
            "feature_keys": ["feature.partner.pricing", "feature.partner.catalog"],
            "module_codes": ["PARTNER_PRICING"],
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_PARTNER_CATALOG,
            "roles": {PARTNER_ROLE},
            "feature_keys": ["feature.partner.catalog", "feature.partner.pricing"],
            "module_codes": ["PARTNER_PRICING"],
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_PARTNER_ORDERS,
            "roles": {PARTNER_ROLE},
            "feature_keys": ["feature.partner.orders"],
            "module_codes": ["PARTNER_ORDERS"],
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_PARTNER_ANALYTICS,
            "roles": {PARTNER_ROLE},
            "feature_keys": ["feature.partner.analytics"],
            "module_codes": ["PARTNER_ANALYTICS"],
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_PARTNER_SETTLEMENTS,
            "roles": {PARTNER_ROLE},
            "feature_keys": ["feature.partner.settlements", "feature.partner.payouts"],
            "module_codes": ["PARTNER_SETTLEMENTS"],
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_PARTNER_FINANCE_VIEW,
            "roles": {PARTNER_ROLE},
            "feature_keys": ["feature.partner.settlements", "feature.partner.payouts"],
            "module_codes": ["PARTNER_SETTLEMENTS"],
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_PARTNER_PAYOUT_REQUEST,
            "roles": {PARTNER_ROLE},
            "feature_keys": ["feature.partner.payouts"],
            "module_codes": ["PARTNER_SETTLEMENTS"],
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_PARTNER_PAYOUT_APPROVAL,
            "roles": {PARTNER_ROLE},
            "feature_keys": ["feature.partner.payouts"],
            "module_codes": ["PARTNER_SETTLEMENTS"],
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_PARTNER_DOCUMENTS_LIST,
            "roles": {PARTNER_ROLE},
            "feature_keys": ["feature.partner.settlements", "feature.partner.payouts"],
            "module_codes": ["PARTNER_SETTLEMENTS"],
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_MARKETPLACE,
            "roles": {CLIENT_ROLE, PARTNER_ROLE},
            "feature_keys": ["feature.marketplace", "feature.portal.marketplace"],
            "module_codes": ["MARKETPLACE"],
            "billing_scoped": False,
        },
        {
            "code": CAPABILITY_LOGISTICS,
            "roles": {CLIENT_ROLE, PARTNER_ROLE},
            "feature_keys": ["feature.logistics"],
            "module_codes": ["LOGISTICS"],
            "billing_scoped": False,
        },
    ]

    role_set = {str(role).upper() for role in org_roles}
    capabilities: list[str] = []
    for rule in rules:
        if not role_set.intersection(rule["roles"]):
            continue
        if rule["billing_scoped"] and billing_blocked:
            continue
        if not _entitlement_allows(features, modules, rule["feature_keys"], rule["module_codes"]):
            continue
        capabilities.append(rule["code"])
    return capabilities


def _apply_support_features(features: dict[str, dict[str, Any]], *, support_plan: str | None, slo_tier: str | None) -> None:
    def maybe_enable(feature_key: str) -> None:
        feature = features.get(feature_key)
        if not feature:
            return
        if feature.get("availability") == AVAILABILITY_DISABLED:
            return
        feature["availability"] = AVAILABILITY_ENABLED

    if support_plan == "DEDICATED":
        maybe_enable("support.priority")
        maybe_enable("support.incident_escalation")

    if slo_tier:
        maybe_enable("slo.tiers")


def _legacy_billing_cycle(plan: dict[str, Any] | None) -> str | None:
    if not plan:
        return None
    try:
        months = int(plan.get("billing_period_months") or 0)
    except (TypeError, ValueError):
        return None
    if months == 12:
        return "YEARLY"
    if months >= 1:
        return "MONTHLY"
    return None


def _legacy_features_from_modules(modules: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    features: dict[str, dict[str, Any]] = {}
    for module_code, payload in modules.items():
        availability = AVAILABILITY_ENABLED if payload.get("enabled") else AVAILABILITY_DISABLED
        for feature_key in LEGACY_MODULE_FEATURE_MAP.get(module_code, set()):
            feature_payload: dict[str, Any] = {"availability": availability}
            limits = payload.get("limits")
            if limits:
                feature_payload["limits"] = limits
            features[feature_key] = feature_payload
    return features


def _apply_legacy_partner_finance_compat(
    *,
    org_roles: list[str],
    features: dict[str, dict[str, Any]],
    modules: dict[str, dict[str, Any]],
) -> None:
    role_set = {str(role).upper() for role in org_roles if role}
    if PARTNER_ROLE not in role_set:
        return
    has_partner_surface = any(str(key).startswith("feature.partner.") for key in features) or any(
        str(code).upper().startswith("PARTNER_") for code in modules
    )
    if has_partner_surface:
        return

    modules["PARTNER_SETTLEMENTS"] = {
        "enabled": True,
        "tier": "legacy-compat",
        "limits": {},
    }
    modules["PARTNER_PRICING"] = {
        "enabled": True,
        "tier": "legacy-compat",
        "limits": {},
    }
    modules["PARTNER_ORDERS"] = {
        "enabled": True,
        "tier": "legacy-compat",
        "limits": {},
    }
    modules["PARTNER_ANALYTICS"] = {
        "enabled": True,
        "tier": "legacy-compat",
        "limits": {},
    }
    features["feature.partner.core"] = {"availability": AVAILABILITY_ENABLED}
    features["feature.partner.catalog"] = {"availability": AVAILABILITY_ENABLED}
    features["feature.partner.pricing"] = {"availability": AVAILABILITY_ENABLED}
    features["feature.partner.orders"] = {"availability": AVAILABILITY_ENABLED}
    features["feature.partner.analytics"] = {"availability": AVAILABILITY_ENABLED}
    features["feature.partner.settlements"] = {"availability": AVAILABILITY_ENABLED}
    features["feature.partner.payouts"] = {"availability": AVAILABILITY_ENABLED}


def _load_legacy_snapshot(
    db: Session,
    *,
    org_id: int,
    computed_at: datetime,
) -> EntitlementsSnapshot | None:
    required_tables = [
        "client_subscriptions",
        "subscription_plans",
        "subscription_plan_modules",
    ]
    if not _tables_ready(db, required_tables):
        return None

    client_subscriptions = _table(db, "client_subscriptions")
    query = select(client_subscriptions).where(client_subscriptions.c.tenant_id == org_id)
    if "created_at" in client_subscriptions.c:
        query = query.order_by(client_subscriptions.c.created_at.desc())
    elif "start_at" in client_subscriptions.c:
        query = query.order_by(client_subscriptions.c.start_at.desc())
    subscription = db.execute(query.limit(1)).mappings().first()
    if not subscription:
        return None

    return _build_legacy_snapshot_from_subscription(
        db,
        subscription=subscription,
        org_id=org_id,
        computed_at=computed_at,
    )


def _load_partner_role_compat_snapshot(
    db: Session,
    *,
    org_id: int,
    computed_at: datetime,
) -> EntitlementsSnapshot | None:
    org_roles = _load_org_roles(db, org_id=org_id)
    if PARTNER_ROLE not in {str(role).upper() for role in org_roles}:
        return None

    features_map: dict[str, dict[str, Any]] = {}
    modules_map: dict[str, dict[str, Any]] = {}
    _apply_legacy_partner_finance_compat(
        org_roles=org_roles,
        features=features_map,
        modules=modules_map,
    )
    if not features_map and not modules_map:
        return None

    capabilities = _compute_capabilities(
        org_roles=org_roles,
        features=features_map,
        modules=modules_map,
        subscription_status=None,
    )
    snapshot_payload = {
        "org_id": org_id,
        "subscription": None,
        "org_roles": org_roles,
        "features": features_map,
        "modules": modules_map,
        "limits": {},
        "capabilities": capabilities,
    }
    payload_hash = _hash_payload(snapshot_payload)
    entitlements = {
        **snapshot_payload,
        "computed": {
            "hash": payload_hash,
            "computed_at": computed_at.isoformat(),
        },
    }
    return EntitlementsSnapshot(
        entitlements=entitlements,
        hash=payload_hash,
        computed_at=computed_at,
        subscription_id=None,
    )


def _build_legacy_snapshot_from_subscription(
    db: Session,
    *,
    subscription: dict[str, Any],
    org_id: int | str,
    computed_at: datetime,
    fallback_roles: list[str] | None = None,
) -> EntitlementsSnapshot | None:
    subscription_plans = _table(db, "subscription_plans")
    plan = (
        db.execute(select(subscription_plans).where(subscription_plans.c.id == subscription["plan_id"]))
        .mappings()
        .first()
    )

    plan_modules = _table(db, "subscription_plan_modules")
    module_rows = (
        db.execute(select(plan_modules).where(plan_modules.c.plan_id == subscription["plan_id"]))
        .mappings()
        .all()
    )
    modules_map: dict[str, dict[str, Any]] = {}
    for row in module_rows:
        module_code = str(row.get("module_code") or "").upper()
        if not module_code:
            continue
        limits = row.get("limits_json")
        if limits is None and "limits" in row:
            limits = row.get("limits")
        modules_map[module_code] = {
            "enabled": bool(row.get("enabled")),
            "tier": row.get("tier"),
            "limits": limits or {},
        }

    features_map = _legacy_features_from_modules(modules_map)
    org_roles = _load_org_roles(db, org_id=org_id) if isinstance(org_id, int) else []
    if not org_roles and fallback_roles:
        org_roles = sorted({str(role).upper() for role in fallback_roles if role})
    if not org_roles:
        org_roles = [CLIENT_ROLE]
    _apply_legacy_partner_finance_compat(
        org_roles=org_roles,
        features=features_map,
        modules=modules_map,
    )

    support_plan_code = None
    slo_tier_code = None
    _apply_support_features(features_map, support_plan=support_plan_code, slo_tier=slo_tier_code)

    subscription_status = _normalize_subscription_status(subscription.get("status"))
    subscription_payload = {
        "plan_code": plan.get("code") if plan else None,
        "plan_version": plan.get("version") if plan and "version" in plan else None,
        "status": subscription_status or (str(subscription.get("status")).upper() if subscription.get("status") else None),
        "billing_cycle": _legacy_billing_cycle(plan),
        "support_plan": support_plan_code,
        "slo_tier": slo_tier_code,
        "addons": [],
    }
    capabilities = _compute_capabilities(
        org_roles=org_roles,
        features=features_map,
        modules=modules_map,
        subscription_status=subscription_status,
    )
    snapshot_payload = {
        "org_id": org_id,
        "subscription": subscription_payload,
        "org_roles": org_roles,
        "features": features_map,
        "modules": modules_map,
        "limits": {},
        "capabilities": capabilities,
    }
    payload_hash = _hash_payload(snapshot_payload)
    entitlements = {
        **snapshot_payload,
        "computed": {
            "hash": payload_hash,
            "computed_at": computed_at.isoformat(),
        },
    }
    return EntitlementsSnapshot(
        entitlements=entitlements,
        hash=payload_hash,
        computed_at=computed_at,
        subscription_id=None,
    )


def get_client_entitlements_snapshot(
    db: Session,
    *,
    client_id: str,
    org_id: int | str | None = None,
) -> EntitlementsSnapshot | None:
    required_tables = [
        "client_subscriptions",
        "subscription_plans",
        "subscription_plan_modules",
    ]
    if not client_id or not _tables_ready(db, required_tables):
        return None

    client_subscriptions = _table(db, "client_subscriptions")
    client_col = client_subscriptions.c.client_id if "client_id" in client_subscriptions.c else None
    if client_col is None:
        return None

    query = select(client_subscriptions).where(cast(client_col, String) == str(client_id))
    if "created_at" in client_subscriptions.c:
        query = query.order_by(client_subscriptions.c.created_at.desc())
    elif "start_at" in client_subscriptions.c:
        query = query.order_by(client_subscriptions.c.start_at.desc())
    subscription = db.execute(query.limit(1)).mappings().first()
    if not subscription:
        return None

    resolved_org_id = org_id if org_id not in (None, "") else client_id
    return _build_legacy_snapshot_from_subscription(
        db,
        subscription=subscription,
        org_id=resolved_org_id,
        computed_at=_now(),
        fallback_roles=[CLIENT_ROLE],
    )


def get_org_entitlements_snapshot(
    db: Session,
    *,
    org_id: int,
    force_new_version: bool = False,
) -> EntitlementsSnapshot:
    required_tables = [
        "org_subscriptions",
        "subscription_plans",
        "subscription_plan_features",
        "subscription_plan_modules",
        "org_subscription_addons",
        "addons",
        "org_subscription_overrides",
        "support_plans",
        "slo_tiers",
        "org_entitlements_snapshot",
    ]
    computed_at = _now()
    legacy_snapshot = _load_legacy_snapshot(db, org_id=org_id, computed_at=computed_at)
    if legacy_snapshot is not None and not _tables_ready(db, required_tables):
        return legacy_snapshot
    if not _tables_ready(db, required_tables):
        partner_role_snapshot = _load_partner_role_compat_snapshot(
            db,
            org_id=org_id,
            computed_at=computed_at,
        )
        if partner_role_snapshot is not None:
            return partner_role_snapshot
        payload = {
            "org_id": org_id,
            "subscription": None,
            "org_roles": [],
            "features": {},
            "modules": {},
            "limits": {},
            "capabilities": [],
            "computed": {
                "hash": "",
                "computed_at": computed_at.isoformat(),
            },
        }
        return EntitlementsSnapshot(
            entitlements=payload,
            hash="",
            computed_at=computed_at,
            subscription_id=None,
        )

    org_subscriptions = _table(db, "org_subscriptions")
    subscription_plans = _table(db, "subscription_plans")
    plan_features = _table(db, "subscription_plan_features")
    plan_modules = _table(db, "subscription_plan_modules")
    addons = _table(db, "addons")
    org_addons = _table(db, "org_subscription_addons")
    overrides = _table(db, "org_subscription_overrides")
    support_plans = _table(db, "support_plans")
    slo_tiers = _table(db, "slo_tiers")
    snapshots = _table(db, "org_entitlements_snapshot")

    subscription = (
        db.execute(
            select(org_subscriptions).where(org_subscriptions.c.org_id == org_id)
        )
        .mappings()
        .first()
    )

    subscription_id = None
    plan = None
    support_plan_code = None
    slo_tier_code = None
    addons_payload: list[dict[str, Any]] = []
    active_addons: set[str] = set()
    features_map: dict[str, dict[str, Any]] = {}
    modules_map: dict[str, dict[str, Any]] = {}

    if subscription:
        subscription_id = subscription["id"]
        plan = (
            db.execute(
                select(subscription_plans).where(subscription_plans.c.id == subscription["plan_id"])
            )
            .mappings()
            .first()
        )
        support_plan_code = None
        if subscription.get("support_plan_id"):
            support_plan = (
                db.execute(
                    select(support_plans).where(support_plans.c.id == subscription["support_plan_id"])
                )
                .mappings()
                .first()
            )
            support_plan_code = support_plan["code"] if support_plan else None
        slo_tier_code = None
        if subscription.get("slo_tier_id"):
            slo_tier = (
                db.execute(select(slo_tiers).where(slo_tiers.c.id == subscription["slo_tier_id"]))
                .mappings()
                .first()
            )
            slo_tier_code = slo_tier["code"] if slo_tier else None

        addon_rows = (
            db.execute(
                select(org_addons.c.status, addons.c.code)
                .join(addons, addons.c.id == org_addons.c.addon_id)
                .where(org_addons.c.org_subscription_id == subscription_id)
            )
            .mappings()
            .all()
        )
        addons_payload = [
            {"code": addon["code"], "status": addon["status"]} for addon in addon_rows
        ]
        active_addons = {
            addon["code"] for addon in addon_rows if addon["status"] == "ACTIVE"
        }

        feature_rows = (
            db.execute(select(plan_features).where(plan_features.c.plan_id == subscription["plan_id"]))
            .mappings()
            .all()
        )
        for row in feature_rows:
            payload = {"availability": row["availability"]}
            if row["limits_json"] is not None:
                payload["limits"] = row["limits_json"]
            features_map[row["feature_key"]] = payload

        module_rows = (
            db.execute(select(plan_modules).where(plan_modules.c.plan_id == subscription["plan_id"]))
            .mappings()
            .all()
        )
        for row in module_rows:
            modules_map[row["module_code"]] = {
                "enabled": row["enabled"],
                "tier": row["tier"],
                "limits": row["limits_json"] or {},
            }

        feature_to_addons = _reverse_addon_map()
        for feature_key, payload in features_map.items():
            if payload.get("availability") != AVAILABILITY_ADDON:
                continue
            eligible_addons = feature_to_addons.get(feature_key, set())
            if active_addons.intersection(eligible_addons):
                payload["availability"] = AVAILABILITY_ENABLED
            else:
                payload["availability"] = AVAILABILITY_DISABLED

        override_rows = (
            db.execute(select(overrides).where(overrides.c.org_subscription_id == subscription_id))
            .mappings()
            .all()
        )
        for override in override_rows:
            payload = {"availability": override["availability"]}
            if override["limits_json"] is not None:
                payload["limits"] = override["limits_json"]
            features_map[override["feature_key"]] = payload

    _apply_support_features(
        features_map,
        support_plan=support_plan_code,
        slo_tier=slo_tier_code,
    )

    subscription_payload: dict[str, Any] | None = None
    if subscription:
        subscription_payload = {
            "plan_code": plan["code"] if plan else None,
            "plan_version": plan["version"] if plan else None,
            "status": subscription["status"],
            "billing_cycle": subscription["billing_cycle"],
            "support_plan": support_plan_code,
            "slo_tier": slo_tier_code,
            "addons": addons_payload,
        }

    org_roles = _load_org_roles(db, org_id=org_id)
    if not org_roles and subscription:
        org_roles = [CLIENT_ROLE]

    subscription_status = _normalize_subscription_status(
        subscription_payload.get("status") if subscription_payload else None
    )
    capabilities = _compute_capabilities(
        org_roles=org_roles,
        features=features_map,
        modules=modules_map,
        subscription_status=subscription_status,
    )

    snapshot_payload = {
        "org_id": org_id,
        "subscription": subscription_payload,
        "org_roles": org_roles,
        "features": features_map,
        "modules": modules_map,
        "limits": {},
        "capabilities": capabilities,
    }
    payload_hash = _hash_payload(snapshot_payload)
    computed_payload = {
        "hash": payload_hash,
        "computed_at": computed_at.isoformat(),
    }
    snapshot_payload["computed"] = computed_payload

    if subscription:
        latest = (
            db.execute(
                select(snapshots.c.hash, snapshots.c.version, snapshots.c.computed_at)
                .where(snapshots.c.org_id == org_id)
                .order_by(snapshots.c.computed_at.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if latest and latest["hash"] == payload_hash and not force_new_version:
            computed_at = latest["computed_at"]
            snapshot_payload["computed"]["computed_at"] = computed_at.isoformat()
        else:
            version = (latest["version"] + 1) if latest else 1
            db.execute(
                insert(snapshots).values(
                    org_id=org_id,
                    subscription_id=subscription_id,
                    entitlements_json=snapshot_payload,
                    hash=payload_hash,
                    version=version,
                    computed_at=computed_at,
                )
            )
            db.commit()

    return EntitlementsSnapshot(
        entitlements=snapshot_payload,
        hash=payload_hash,
        computed_at=computed_at,
        subscription_id=subscription_id,
    )
