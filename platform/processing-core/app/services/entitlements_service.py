from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from app.models.client_cards import ClientCard
from app.models.pricing import PriceVersionItem
from app.models.subscriptions_v1 import ClientSubscription, SubscriptionPlan, SubscriptionPlanLimit, SubscriptionPlanModule
from app.db.schema import DB_SCHEMA
from app.services.pricing_versions import get_active_price_version


_ENTITLEMENTS_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_ENTITLEMENTS_CACHE_MAX = 512


@dataclass(frozen=True)
class Entitlements:
    plan_code: str
    price_version_id: str | None
    modules: dict[str, dict[str, Any]]
    limits: dict[str, dict[str, Any]]
    pricing: dict[str, Any] | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _subscription_tables_ready(db: Session) -> bool:
    try:
        inspector = inspect(db.get_bind())
        return inspector.has_table("subscription_plans", schema=DB_SCHEMA)
    except Exception:
        return False


def _cache_get(key: str) -> dict[str, Any] | None:
    value = _ENTITLEMENTS_CACHE.get(key)
    if value is None:
        return None
    _ENTITLEMENTS_CACHE.move_to_end(key)
    return value


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    _ENTITLEMENTS_CACHE[key] = payload
    _ENTITLEMENTS_CACHE.move_to_end(key)
    if len(_ENTITLEMENTS_CACHE) > _ENTITLEMENTS_CACHE_MAX:
        _ENTITLEMENTS_CACHE.popitem(last=False)


def _make_cache_key(*, client_id: str, plan_code: str, price_version_id: str | None, limits_hash: str) -> str:
    return f"{client_id}:{plan_code}:{price_version_id or 'none'}:{limits_hash}"


def _limits_hash(modules: list[SubscriptionPlanModule], limits: list[SubscriptionPlanLimit]) -> str:
    payload = {
        "modules": [
            {"code": module.module_code.value, "enabled": module.enabled, "limits": module.limits}
            for module in modules
        ],
        "limits": [
            {
                "code": limit.limit_code,
                "period": limit.period,
                "value_int": limit.value_int,
                "value_decimal": str(limit.value_decimal) if limit.value_decimal is not None else None,
                "value_text": limit.value_text,
                "value_json": limit.value_json,
            }
            for limit in limits
        ],
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _get_subscription(db: Session, *, client_id: str) -> ClientSubscription | None:
    return (
        db.query(ClientSubscription)
        .filter(ClientSubscription.client_id == client_id)
        .order_by(ClientSubscription.created_at.desc())
        .first()
    )


def _build_entitlements(
    db: Session,
    *,
    client_id: str,
    subscription: ClientSubscription,
    plan: SubscriptionPlan,
    price_version_id: str | None,
) -> dict[str, Any]:
    modules = db.query(SubscriptionPlanModule).filter(SubscriptionPlanModule.plan_id == plan.id).all()
    limits = db.query(SubscriptionPlanLimit).filter(SubscriptionPlanLimit.plan_id == plan.id).all()

    modules_payload = {
        module.module_code.value: {"enabled": module.enabled, "tier": module.tier, "limits": module.limits or {}}
        for module in modules
    }
    limits_payload = {}
    for limit in limits:
        limits_payload[limit.limit_code] = {
            "period": limit.period,
            "value_int": limit.value_int,
            "value_decimal": str(limit.value_decimal) if limit.value_decimal is not None else None,
            "value_text": limit.value_text,
            "value_json": limit.value_json,
        }

    pricing_payload = None
    if price_version_id:
        item = (
            db.query(PriceVersionItem)
            .filter(
                PriceVersionItem.price_version_id == price_version_id,
                PriceVersionItem.plan_code == plan.code,
            )
            .first()
        )
        if item:
            pricing_payload = {
                "billing_period": item.billing_period,
                "currency": item.currency,
                "base_price": str(item.base_price),
                "setup_fee": str(item.setup_fee) if item.setup_fee is not None else None,
            }

    return {
        "client_id": client_id,
        "plan_code": plan.code,
        "plan_id": plan.id,
        "price_version_id": price_version_id,
        "modules": modules_payload,
        "limits": limits_payload,
        "pricing": pricing_payload,
    }


def get_entitlements(db: Session, *, client_id: str) -> Entitlements:
    if not _subscription_tables_ready(db):
        return Entitlements(plan_code="UNKNOWN", price_version_id=None, modules={}, limits={}, pricing=None)
    subscription = _get_subscription(db, client_id=client_id)
    if subscription is None:
        from app.services.subscription_service import DEFAULT_TENANT_ID, ensure_free_subscription

        subscription = ensure_free_subscription(db, tenant_id=DEFAULT_TENANT_ID, client_id=client_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    plan = db.get(SubscriptionPlan, subscription.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan_not_found")

    active_version = get_active_price_version(db, at=_now())
    price_version_id = active_version.id if active_version else subscription.current_price_version_id

    modules = db.query(SubscriptionPlanModule).filter(SubscriptionPlanModule.plan_id == plan.id).all()
    limits = db.query(SubscriptionPlanLimit).filter(SubscriptionPlanLimit.plan_id == plan.id).all()
    limits_hash = _limits_hash(modules, limits)
    cache_key = _make_cache_key(
        client_id=client_id, plan_code=plan.code, price_version_id=price_version_id, limits_hash=limits_hash
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        return Entitlements(
            plan_code=cached["plan_code"],
            price_version_id=cached["price_version_id"],
            modules=cached["modules"],
            limits=cached["limits"],
            pricing=cached["pricing"],
        )

    payload = _build_entitlements(
        db,
        client_id=client_id,
        subscription=subscription,
        plan=plan,
        price_version_id=price_version_id,
    )
    _cache_set(cache_key, payload)
    return Entitlements(
        plan_code=payload["plan_code"],
        price_version_id=payload["price_version_id"],
        modules=payload["modules"],
        limits=payload["limits"],
        pricing=payload["pricing"],
    )


def assert_module_enabled(db: Session, *, client_id: str, module_code: str) -> None:
    if not _subscription_tables_ready(db):
        return
    entitlements = get_entitlements(db, client_id=client_id)
    module = entitlements.modules.get(module_code)
    if not module or not module.get("enabled"):
        raise HTTPException(status_code=403, detail="feature_not_included")


def _limit_value(limit: dict[str, Any]) -> int | Decimal | None:
    if limit.get("value_int") is not None:
        return int(limit["value_int"])
    if limit.get("value_decimal") is not None:
        return Decimal(limit["value_decimal"])
    return None


def assert_limit(
    db: Session,
    *,
    client_id: str,
    limit_code: str,
    current_value: int,
    delta: int = 1,
) -> None:
    if not _subscription_tables_ready(db):
        return
    entitlements = get_entitlements(db, client_id=client_id)
    limit = entitlements.limits.get(limit_code)
    if not limit:
        return
    limit_value = _limit_value(limit)
    if limit_value is None:
        return
    if current_value + delta > limit_value:
        raise HTTPException(status_code=403, detail="limit_exceeded")


def assert_max_cards(db: Session, *, client_id: str, delta: int = 1) -> None:
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        client_uuid = None
    query = db.query(func.count(ClientCard.id))
    if client_uuid:
        query = query.filter(ClientCard.client_id == client_uuid)
    current_cards = int(query.scalar() or 0)
    assert_limit(db, client_id=client_id, limit_code="max_cards", current_value=current_cards, delta=delta)


__all__ = ["Entitlements", "assert_limit", "assert_max_cards", "assert_module_enabled", "get_entitlements"]
