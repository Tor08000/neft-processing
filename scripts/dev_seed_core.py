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

from sqlalchemy import MetaData, Table, insert, inspect, select, text, update

ROOT = Path(__file__).resolve().parents[1]
PROCESSING_ROOT = ROOT / "platform" / "processing-core"
SHARED = ROOT / "shared" / "python"

for path in (PROCESSING_ROOT, SHARED):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.db import get_sessionmaker, init_db  # noqa: E402
from app.db.schema import DB_SCHEMA  # noqa: E402
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


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


_COLUMNS_CACHE: dict[tuple[str, str], set[str]] = {}


def has_column(conn, table: str, column: str, schema: str = "processing_core") -> bool:
    cache_key = (schema, table)
    if cache_key not in _COLUMNS_CACHE:
        rows = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = :table
                """
            ),
            {"schema": schema, "table": table},
        ).fetchall()
        _COLUMNS_CACHE[cache_key] = {row[0] for row in rows}
    return column in _COLUMNS_CACHE[cache_key]


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


def _ensure_client(conn, config: DemoSeedConfig, *, has_client_email: bool) -> str:
    if not _is_uuid(config.client_id):
        raise ValueError(f"NEFT_DEMO_CLIENT_UUID must be a UUID, got {config.client_id!r}")
    if not _table_exists(conn, "clients"):
        return "skipped_missing_table"
    clients = _table(conn, "clients")
    existing = conn.execute(select(clients).where(clients.c.id == config.client_id)).mappings().first()
    if existing:
        update_values: dict[str, Any] = {}
        if _is_empty_value(existing.get("name")):
            update_values["name"] = "Demo Client"
        if _is_empty_value(existing.get("full_name")):
            update_values["full_name"] = "Demo Client"
        if _is_empty_value(existing.get("status")):
            update_values["status"] = "ACTIVE"
        if _is_empty_value(existing.get("external_id")):
            update_values["external_id"] = config.org_name
        if has_client_email and _is_empty_value(existing.get("email")):
            update_values["email"] = config.email
        update_values = _filter_columns(clients, update_values)
        if update_values:
            conn.execute(update(clients).where(clients.c.id == config.client_id).values(**update_values))
        return "updated"
    values = {
        "id": config.client_id,
        "name": "Demo Client",
        "external_id": config.org_name,
        "full_name": "Demo Client",
        "status": "ACTIVE",
    }
    if has_client_email:
        values["email"] = config.email
    values = _filter_columns(clients, values)
    conn.execute(insert(clients).values(**values))
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




def _ensure_demo_fuel_stations(engine) -> str:
    if not _table_exists(engine, "fuel_networks") or not _table_exists(engine, "fuel_stations"):
        return "skipped_missing_table"

    networks = _table(engine, "fuel_networks")
    stations = _table(engine, "fuel_stations")
    now = _now()

    provider_code = "demo_geo_network"
    network = engine.execute(select(networks).where(networks.c.provider_code == provider_code)).mappings().first()
    if network:
        network_id = str(network["id"])
    else:
        network_id = str(uuid4())
        network_values = _filter_columns(
            networks,
            {
                "id": network_id,
                "name": "Demo Geo Fuel Network",
                "provider_code": provider_code,
                "status": "ACTIVE",
                "created_at": now,
            },
        )
        engine.execute(insert(networks).values(**network_values))

    city_points: list[tuple[str, str, str, float, float]] = [
        ("Moscow", "Moscow", "ул. Тверская", 55.7558, 37.6176),
        ("Moscow", "Moscow", "Ленинградский проспект", 55.7903, 37.5451),
        ("Moscow", "Moscow", "Кутузовский проспект", 55.7408, 37.5313),
        ("Moscow", "Moscow", "Варшавское шоссе", 55.6406, 37.6208),
        ("Moscow", "Moscow", "Профсоюзная улица", 55.6717, 37.5514),
        ("Moscow", "Moscow", "Волгоградский проспект", 55.7115, 37.6953),
        ("Moscow", "Moscow", "Рязанский проспект", 55.7163, 37.7822),
        ("Moscow", "Moscow", "Дмитровское шоссе", 55.8688, 37.5432),
        ("Moscow", "Moscow", "Алтуфьевское шоссе", 55.8765, 37.5881),
        ("Moscow", "Moscow", "МКАД 65 км", 55.8404, 37.3867),
        ("Saint Petersburg", "Saint Petersburg", "Невский проспект", 59.9343, 30.3351),
        ("Saint Petersburg", "Saint Petersburg", "Московский проспект", 59.8790, 30.3186),
        ("Saint Petersburg", "Saint Petersburg", "Лиговский проспект", 59.9202, 30.3557),
        ("Saint Petersburg", "Saint Petersburg", "Пулковское шоссе", 59.8102, 30.3176),
        ("Saint Petersburg", "Saint Petersburg", "Приморский проспект", 59.9846, 30.2508),
        ("Saint Petersburg", "Saint Petersburg", "Богатырский проспект", 60.0048, 30.2629),
        ("Saint Petersburg", "Saint Petersburg", "Индустриальный проспект", 59.9487, 30.4712),
        ("Saint Petersburg", "Saint Petersburg", "КАД 32 км", 59.8589, 30.1842),
        ("Saint Petersburg", "Saint Petersburg", "Пискаревский проспект", 59.9896, 30.4231),
        ("Saint Petersburg", "Saint Petersburg", "Выборгское шоссе", 60.0662, 30.3034),
    ]

    updated = 0
    created = 0
    for idx, (region, city, street, lat, lon) in enumerate(city_points, start=1):
        station_code = f"DEMO-GEO-{idx:03d}"
        station_name = f"Demo Station {idx:03d}"
        station_address = f"{city}, {street}"
        existing = (
            engine.execute(
                select(stations).where(stations.c.network_id == network_id, stations.c.station_code == station_code)
            )
            .mappings()
            .first()
        )
        values = _filter_columns(
            stations,
            {
                "network_id": network_id,
                "station_code": station_code,
                "name": station_name,
                "country": "RU",
                "region": region,
                "city": city,
                "lat": lat,
                "lon": lon,
                "status": "ACTIVE",
                "mcc": "5541",
                "nav_url": None,
                "geo_hash": None,
                "created_at": now,
                "meta": {"address": station_address},
            },
        )
        if existing:
            engine.execute(
                update(stations)
                .where(stations.c.network_id == network_id, stations.c.station_code == station_code)
                .values(**values)
            )
            updated += 1
        else:
            values["id"] = str(uuid4())
            engine.execute(insert(stations).values(**values))
            created += 1

    return f"created={created},updated={updated}"
def main() -> None:
    config = _load_config()
    init_db()
    SessionLocal = get_sessionmaker()

    summary: dict[str, Any] = {"items": []}

    def _record(label: str, status: str) -> None:
        summary["items"].append({"item": label, "status": status})

    with SessionLocal() as session:
        conn = session.connection()
        has_client_email = has_column(conn, "clients", "email")
        _record("client", _ensure_client(conn, config, has_client_email=has_client_email))
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
        _record("fuel_demo_stations", _ensure_demo_fuel_stations(engine))

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
