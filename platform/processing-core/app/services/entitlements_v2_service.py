from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import MetaData, Table, insert, inspect, select
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


@dataclass(frozen=True)
class EntitlementsSnapshot:
    entitlements: dict[str, Any]
    hash: str
    computed_at: datetime
    subscription_id: int | None


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tables_ready(db: Session, table_names: list[str]) -> bool:
    try:
        inspector = inspect(db.get_bind())
        return all(inspector.has_table(name, schema=DB_SCHEMA) for name in table_names)
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


def get_org_entitlements_snapshot(db: Session, *, org_id: int) -> EntitlementsSnapshot:
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
    if not _tables_ready(db, required_tables):
        payload = {
            "org_id": org_id,
            "subscription": None,
            "features": {},
            "modules": {},
            "limits": {},
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

    snapshot_payload = {
        "org_id": org_id,
        "subscription": subscription_payload,
        "features": features_map,
        "modules": modules_map,
        "limits": {},
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
        if latest and latest["hash"] == payload_hash:
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
