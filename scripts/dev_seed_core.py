#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, insert, inspect, select, update

ROOT = Path(__file__).resolve().parents[1]
PROCESSING_ROOT = ROOT / "platform" / "processing-core"
SHARED = ROOT / "shared" / "python"

for path in (PROCESSING_ROOT, SHARED):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.db import get_sessionmaker, init_db  # noqa: E402
from app.db.schema import DB_SCHEMA  # noqa: E402
from app.models.client import Client  # noqa: E402
from app.models.fleet import ClientEmployee, EmployeeStatus  # noqa: E402
from app.models.client_portal import ClientUserRole  # noqa: E402
from app.services.entitlements_v2_service import get_org_entitlements_snapshot  # noqa: E402


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _table(engine, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=engine, schema=DB_SCHEMA)


def _table_exists(engine, name: str) -> bool:
    inspector = inspect(engine)
    return inspector.has_table(name, schema=DB_SCHEMA)


def _filter_columns(table: Table, values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key in table.c}


@dataclass(frozen=True)
class DemoSeedConfig:
    org_id: int
    client_id: str
    user_id: str
    email: str
    org_name: str
    plan_code: str
    plan_title: str


def _load_config() -> DemoSeedConfig:
    org_id = int(os.getenv("NEFT_DEMO_ORG_ID", "1"))
    client_id = os.getenv("NEFT_DEMO_CLIENT_UUID", "00000000-0000-0000-0000-000000000001")
    email = os.getenv("NEFT_DEMO_CLIENT_EMAIL", "client@neft.local")
    org_name = os.getenv("NEFT_DEMO_ORG_NAME", "demo-client")
    plan_code = os.getenv("NEFT_DEMO_PLAN_CODE", "DEMO")
    plan_title = os.getenv("NEFT_DEMO_PLAN_TITLE", "Demo")
    return DemoSeedConfig(
        org_id=org_id,
        client_id=client_id,
        user_id=client_id,
        email=email,
        org_name=org_name,
        plan_code=plan_code,
        plan_title=plan_title,
    )


def _ensure_client(session, config: DemoSeedConfig) -> str:
    if not _is_uuid(config.client_id):
        raise ValueError(f"NEFT_DEMO_CLIENT_UUID must be a UUID, got {config.client_id!r}")
    client = session.get(Client, config.client_id)
    if client:
        client.name = client.name or "Demo Client"
        client.email = client.email or config.email
        client.status = client.status or "ACTIVE"
        return "noop"
    client = Client(
        id=config.client_id,
        name="Demo Client",
        external_id=config.org_name,
        email=config.email,
        full_name="Demo Client",
        status="ACTIVE",
    )
    session.add(client)
    return "created"


def _ensure_client_employee(session, config: DemoSeedConfig) -> str:
    if not _is_uuid(config.user_id):
        raise ValueError(f"DEMO user_id must be a UUID, got {config.user_id!r}")
    employee = session.get(ClientEmployee, config.user_id)
    if employee:
        employee.client_id = config.client_id
        employee.email = config.email
        employee.status = EmployeeStatus.ACTIVE
        return "updated"
    employee = ClientEmployee(
        id=config.user_id,
        client_id=config.client_id,
        email=config.email,
        status=EmployeeStatus.ACTIVE,
        timezone="UTC",
    )
    session.add(employee)
    return "created"


def _ensure_client_role(session, config: DemoSeedConfig) -> str:
    role = (
        session.query(ClientUserRole)
        .filter(ClientUserRole.client_id == config.client_id, ClientUserRole.user_id == config.user_id)
        .one_or_none()
    )
    if role:
        role.roles = "CLIENT_OWNER"
        return "updated"
    session.add(
        ClientUserRole(
            client_id=config.client_id,
            user_id=config.user_id,
            roles="CLIENT_OWNER",
        )
    )
    return "created"


def _ensure_org(engine, config: DemoSeedConfig) -> str:
    if not _table_exists(engine, "orgs"):
        return "skipped_missing_table"
    orgs = _table(engine, "orgs")
    existing = engine.execute(select(orgs).where(orgs.c.id == config.org_id)).mappings().first()
    values = {
        "id": config.org_id,
        "name": config.org_name,
        "status": "ACTIVE",
        "roles": json.dumps(["CLIENT"]),
        "created_at": _now(),
        "updated_at": _now(),
    }
    values = _filter_columns(orgs, values)
    if existing:
        engine.execute(update(orgs).where(orgs.c.id == config.org_id).values(**values))
        return "updated"
    engine.execute(insert(orgs).values(**values))
    return "created"


def _ensure_subscription_plan(engine, config: DemoSeedConfig) -> tuple[str | None, str]:
    if not _table_exists(engine, "subscription_plans"):
        return None, "skipped_missing_table"
    plans = _table(engine, "subscription_plans")
    existing = engine.execute(select(plans).where(plans.c.code == config.plan_code)).mappings().first()
    if existing:
        return str(existing.get("id")), "noop"

    plan_id = str(uuid4())
    values = {
        "id": plan_id,
        "code": config.plan_code,
        "version": 1,
        "title": config.plan_title,
        "description": "Demo plan for dev bootstrap",
        "is_active": True,
        "is_hidden": False,
        "billing_period_months": 1,
        "billing_cycle": "MONTHLY",
        "price_cents": 0,
        "discount_percent": 0,
        "currency": "RUB",
        "created_at": _now(),
        "updated_at": _now(),
    }
    values = _filter_columns(plans, values)
    engine.execute(insert(plans).values(**values))
    return plan_id, "created"


def _ensure_plan_features(engine, plan_id: str | None) -> dict[str, str]:
    results: dict[str, str] = {}
    if not plan_id or not _table_exists(engine, "subscription_plan_features"):
        return {"status": "skipped_missing_table"}
    features = _table(engine, "subscription_plan_features")
    now = _now()
    feature_keys = [
        "feature.portal.core",
        "feature.portal.entities",
        "feature.portal.billing",
        "feature.billing.invoices",
        "feature.portal.cards",
    ]
    for feature_key in feature_keys:
        existing = (
            engine.execute(
                select(features).where(
                    features.c.plan_id == plan_id,
                    features.c.feature_key == feature_key,
                )
            )
            .mappings()
            .first()
        )
        values = {
            "plan_id": plan_id,
            "feature_key": feature_key,
            "availability": "ENABLED",
            "limits_json": None,
            "created_at": now,
            "updated_at": now,
        }
        values = _filter_columns(features, values)
        if existing:
            engine.execute(
                update(features)
                .where(features.c.plan_id == plan_id, features.c.feature_key == feature_key)
                .values(**values)
            )
            results[feature_key] = "updated"
        else:
            engine.execute(insert(features).values(**values))
            results[feature_key] = "created"
    return results


def _ensure_org_subscription(engine, config: DemoSeedConfig, plan_id: str | None) -> str:
    if not plan_id or not _table_exists(engine, "org_subscriptions"):
        return "skipped_missing_table"
    org_subscriptions = _table(engine, "org_subscriptions")
    existing = (
        engine.execute(select(org_subscriptions).where(org_subscriptions.c.org_id == config.org_id))
        .mappings()
        .first()
    )
    now = _now()
    values = {
        "org_id": config.org_id,
        "plan_id": plan_id,
        "status": "ACTIVE",
        "billing_cycle": "MONTHLY",
        "created_at": now,
        "updated_at": now,
        "effective_at": now,
        "start_at": now,
        "starts_at": now,
        "grace_period_days": 0,
    }
    values = _filter_columns(org_subscriptions, values)
    if existing:
        engine.execute(update(org_subscriptions).where(org_subscriptions.c.id == existing["id"]).values(**values))
        return "updated"
    engine.execute(insert(org_subscriptions).values(**values))
    return "created"


def main() -> None:
    config = _load_config()
    init_db()
    SessionLocal = get_sessionmaker()

    summary: dict[str, Any] = {"items": []}

    def _record(label: str, status: str) -> None:
        summary["items"].append({"item": label, "status": status})

    with SessionLocal() as session:
        _record("client", _ensure_client(session, config))
        _record("client_employee", _ensure_client_employee(session, config))
        _record("client_role", _ensure_client_role(session, config))
        session.commit()

        engine = session.get_bind()
        _record("org", _ensure_org(engine, config))
        plan_id, plan_status = _ensure_subscription_plan(engine, config)
        _record("subscription_plan", plan_status)
        feature_results = _ensure_plan_features(engine, plan_id)
        for feature_key, status in feature_results.items():
            _record(f"plan_feature:{feature_key}", status)
        _record("org_subscription", _ensure_org_subscription(engine, config, plan_id))

        if plan_id:
            get_org_entitlements_snapshot(session, org_id=config.org_id)
        session.commit()

    summary.update(
        {
            "client_id": config.client_id,
            "user_id": config.user_id,
            "org_id": config.org_id,
            "plan_code": config.plan_code,
        }
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
