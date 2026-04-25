from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    event,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.db.schema import DB_SCHEMA
from app.main import app
from app.routers.admin import commercial as commercial_router


ORG_ID = 101
SUBSCRIPTION_ID = 5001
PLAN_BASIC_ID = "plan-basic"
PLAN_PREMIUM_ID = "plan-premium"
ADDON_HELPDESK_ID = 11
ADDON_WEBHOOKS_ID = 12
BASELINE_FEATURE_KEY = "feature.portal.analytics"


@pytest.fixture(autouse=True)
def allow_mock_providers_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")


@pytest.fixture()
def db_session_factory(monkeypatch: pytest.MonkeyPatch) -> tuple[sessionmaker[Session], dict[str, Table]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_processing_core(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"ATTACH DATABASE ':memory:' AS {DB_SCHEMA}")
        cursor.close()

    tables = _build_commercial_tables()
    tables["orgs"].metadata.create_all(bind=engine)

    testing_session_local = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(commercial_router, "pg_insert", sqlite_insert)
    monkeypatch.setattr(commercial_router.AuditService, "audit", lambda self, **kwargs: None)
    try:
        yield testing_session_local, tables
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _build_commercial_tables(
    *,
    include_snapshot_table: bool = True,
    include_feature_catalog: bool = True,
    include_org_roles_column: bool = True,
    include_support_plan_column: bool = True,
    include_slo_tier_column: bool = True,
) -> dict[str, Table]:
    metadata = MetaData()

    org_columns = [
        Column("id", Integer, primary_key=True),
        Column("name", String(128), nullable=True),
        Column("status", String(32), nullable=True),
    ]
    if include_org_roles_column:
        org_columns.append(Column("roles", JSON, nullable=True))

    subscription_columns = [
        Column("id", Integer, primary_key=True),
        Column("org_id", Integer, nullable=False),
        Column("plan_id", String(64), nullable=False),
        Column("status", String(32), nullable=False),
        Column("billing_cycle", String(32), nullable=True),
    ]
    if include_support_plan_column:
        subscription_columns.append(Column("support_plan_id", Integer, nullable=True))
    if include_slo_tier_column:
        subscription_columns.append(Column("slo_tier_id", Integer, nullable=True))

    tables: dict[str, Table] = {
        "orgs": Table("orgs", metadata, *org_columns, schema=DB_SCHEMA),
        "org_subscriptions": Table(
            "org_subscriptions",
            metadata,
            *subscription_columns,
            schema=DB_SCHEMA,
        ),
        "subscription_plans": Table(
            "subscription_plans",
            metadata,
            Column("id", String(64), primary_key=True),
            Column("code", String(64), nullable=False),
            Column("version", Integer, nullable=False),
            schema=DB_SCHEMA,
        ),
        "subscription_plan_modules": Table(
            "subscription_plan_modules",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("plan_id", String(64), nullable=False),
            Column("module_code", String(64), nullable=False),
            Column("enabled", Integer, nullable=False),
            Column("tier", String(64), nullable=True),
            Column("limits_json", JSON, nullable=True),
            schema=DB_SCHEMA,
        ),
        "org_subscription_addons": Table(
            "org_subscription_addons",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("org_subscription_id", Integer, nullable=False),
            Column("addon_id", Integer, nullable=False),
            Column("status", String(32), nullable=False),
            Column("price_override", Numeric(12, 2), nullable=True),
            Column("starts_at", DateTime(timezone=True), nullable=True),
            Column("ends_at", DateTime(timezone=True), nullable=True),
            Column("config_json", JSON, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=True),
            Column("updated_at", DateTime(timezone=True), nullable=True),
            UniqueConstraint("org_subscription_id", "addon_id", name="uq_org_subscription_addon"),
            schema=DB_SCHEMA,
        ),
        "addons": Table(
            "addons",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("code", String(128), nullable=False),
            schema=DB_SCHEMA,
        ),
        "org_subscription_overrides": Table(
            "org_subscription_overrides",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("org_subscription_id", Integer, nullable=False),
            Column("feature_key", String(128), nullable=False),
            Column("availability", String(32), nullable=False),
            Column("limits_json", JSON, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=True),
            Column("updated_at", DateTime(timezone=True), nullable=True),
            UniqueConstraint("org_subscription_id", "feature_key", name="uq_org_subscription_override"),
            schema=DB_SCHEMA,
        ),
        "support_plans": Table(
            "support_plans",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("code", String(64), nullable=False),
            schema=DB_SCHEMA,
        ),
        "slo_tiers": Table(
            "slo_tiers",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("code", String(64), nullable=False),
            schema=DB_SCHEMA,
        ),
    }
    if include_feature_catalog:
        tables["subscription_plan_features"] = Table(
            "subscription_plan_features",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("plan_id", String(64), nullable=False),
            Column("feature_key", String(128), nullable=False),
            Column("availability", String(32), nullable=False),
            Column("limits_json", JSON, nullable=True),
            schema=DB_SCHEMA,
        )
    if include_snapshot_table:
        tables["org_entitlements_snapshot"] = Table(
            "org_entitlements_snapshot",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("org_id", Integer, nullable=False),
            Column("subscription_id", Integer, nullable=True),
            Column("entitlements_json", JSON, nullable=False),
            Column("hash", String(128), nullable=False),
            Column("version", Integer, nullable=False),
            Column("computed_at", DateTime(timezone=True), nullable=False),
            schema=DB_SCHEMA,
        )
    return tables


def _seed_commercial_state(db: Session, tables: dict[str, Table], *, include_snapshots: bool = True) -> None:
    now = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)
    org_values: dict[str, object] = {
        "id": ORG_ID,
        "name": "Acme Fleet",
        "status": "ACTIVE",
    }
    if "roles" in tables["orgs"].c:
        org_values["roles"] = ["CLIENT"]
    db.execute(tables["orgs"].insert().values(**org_values))
    db.execute(
        tables["subscription_plans"].insert(),
        [
            {"id": PLAN_BASIC_ID, "code": "BASIC", "version": 1},
            {"id": PLAN_PREMIUM_ID, "code": "PREMIUM", "version": 2},
        ],
    )
    db.execute(tables["support_plans"].insert().values(id=1, code="DEDICATED"))
    db.execute(tables["slo_tiers"].insert().values(id=1, code="GOLD"))
    subscription_values: dict[str, object] = {
        "id": SUBSCRIPTION_ID,
        "org_id": ORG_ID,
        "plan_id": PLAN_BASIC_ID,
        "status": "ACTIVE",
        "billing_cycle": "MONTHLY",
    }
    if "support_plan_id" in tables["org_subscriptions"].c:
        subscription_values["support_plan_id"] = 1
    if "slo_tier_id" in tables["org_subscriptions"].c:
        subscription_values["slo_tier_id"] = 1
    db.execute(tables["org_subscriptions"].insert().values(**subscription_values))
    if "subscription_plan_features" in tables:
        db.execute(
            tables["subscription_plan_features"].insert(),
            [
                {"plan_id": PLAN_BASIC_ID, "feature_key": "feature.portal.core", "availability": "ENABLED", "limits_json": None},
                {"plan_id": PLAN_BASIC_ID, "feature_key": "feature.portal.entities", "availability": "ENABLED", "limits_json": None},
                {"plan_id": PLAN_BASIC_ID, "feature_key": BASELINE_FEATURE_KEY, "availability": "ENABLED", "limits_json": {"dashboards": 1}},
                {"plan_id": PLAN_BASIC_ID, "feature_key": "feature.marketplace", "availability": "ADDON_ELIGIBLE", "limits_json": None},
                {"plan_id": PLAN_PREMIUM_ID, "feature_key": "feature.portal.core", "availability": "ENABLED", "limits_json": None},
                {"plan_id": PLAN_PREMIUM_ID, "feature_key": "feature.portal.entities", "availability": "ENABLED", "limits_json": None},
                {"plan_id": PLAN_PREMIUM_ID, "feature_key": BASELINE_FEATURE_KEY, "availability": "ENABLED", "limits_json": {"dashboards": 10}},
            ],
        )
    db.execute(
        tables["subscription_plan_modules"].insert(),
        [
            {"plan_id": PLAN_BASIC_ID, "module_code": "ANALYTICS", "enabled": 1, "tier": "BASIC", "limits_json": {"dashboards": 1}},
            {"plan_id": PLAN_PREMIUM_ID, "module_code": "ANALYTICS", "enabled": 1, "tier": "PREMIUM", "limits_json": {"dashboards": 10}},
        ],
    )
    db.execute(
        tables["addons"].insert(),
        [
            {"id": ADDON_HELPDESK_ID, "code": "integration.helpdesk.zendesk"},
            {"id": ADDON_WEBHOOKS_ID, "code": "integration.api.webhooks"},
        ],
    )
    db.execute(
        tables["org_subscription_addons"].insert().values(
            org_subscription_id=SUBSCRIPTION_ID,
            addon_id=ADDON_HELPDESK_ID,
            status="ACTIVE",
            price_override=Decimal("99.50"),
            starts_at=now,
            ends_at=None,
            config_json={"channel": "priority"},
            created_at=now,
            updated_at=now,
        )
    )
    db.execute(
        tables["org_subscription_overrides"].insert().values(
            org_subscription_id=SUBSCRIPTION_ID,
            feature_key=BASELINE_FEATURE_KEY,
            availability="LIMITED",
            limits_json={"dashboards": 2},
            created_at=now,
            updated_at=now,
        )
    )
    if include_snapshots and "org_entitlements_snapshot" in tables:
        db.execute(
            tables["org_entitlements_snapshot"].insert(),
            [
                {
                    "org_id": ORG_ID,
                    "subscription_id": SUBSCRIPTION_ID,
                    "entitlements_json": {"capabilities": ["CLIENT_CORE"]},
                    "hash": "snapshot-hash-1",
                    "version": 1,
                    "computed_at": datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
                },
                {
                    "org_id": ORG_ID,
                    "subscription_id": SUBSCRIPTION_ID,
                    "entitlements_json": {"capabilities": ["CLIENT_CORE", "CLIENT_ANALYTICS"]},
                    "hash": "snapshot-hash-2",
                    "version": 2,
                    "computed_at": datetime(2026, 4, 6, 10, 0, tzinfo=timezone.utc),
                },
            ],
        )
    db.commit()


def _admin_headers(make_jwt, *roles: str) -> dict[str, str]:
    token = make_jwt(roles=roles, sub="admin-1")
    return {"Authorization": f"Bearer {token}"}


def test_admin_commercial_state_allows_read_role_and_returns_live_shape(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "NEFT_SUPPORT")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.get(f"/api/core/v1/admin/commercial/orgs/{ORG_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["org"]["id"] == ORG_ID
    assert body["org"]["name"] == "Acme Fleet"
    assert body["subscription"]["plan_code"] == "BASIC"
    assert body["subscription"]["plan_version"] == 1
    assert body["subscription"]["support_plan"] == "DEDICATED"
    assert body["subscription"]["slo_tier"] == "GOLD"
    assert body["addons"][0]["addon_code"] == "integration.helpdesk.zendesk"
    assert body["overrides"][0]["feature_key"] == BASELINE_FEATURE_KEY
    assert body["entitlements_snapshot"]["hash"] == "snapshot-hash-2"


def test_admin_commercial_entitlements_returns_current_and_previous_snapshots(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "NEFT_SUPPORT")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.get(f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/entitlements")

    assert response.status_code == 200
    body = response.json()
    assert body["current"]["hash"] == "snapshot-hash-2"
    assert body["previous"][0]["hash"] == "snapshot-hash-1"
    assert body["current"]["entitlements"]["capabilities"] == ["CLIENT_CORE", "CLIENT_ANALYTICS"]


def test_admin_commercial_entitlements_without_snapshot_table_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
    make_jwt,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_processing_core(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"ATTACH DATABASE ':memory:' AS {DB_SCHEMA}")
        cursor.close()

    tables = _build_commercial_tables(include_snapshot_table=False)
    tables["orgs"].metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(commercial_router, "pg_insert", sqlite_insert)
    monkeypatch.setattr(commercial_router.AuditService, "audit", lambda self, **kwargs: None)
    try:
        with SessionLocal() as db:
            _seed_commercial_state(db, tables, include_snapshots=False)

        headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPPORT")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.get(f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/entitlements")

        assert response.status_code == 200
        assert response.json() == {"current": None, "previous": []}
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_admin_commercial_plan_change_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/plan",
            json={
                "plan_code": "PREMIUM",
                "plan_version": 2,
                "billing_cycle": "YEARLY",
                "status": "ACTIVE",
                "reason": "upgrade",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["plan_code"] == "PREMIUM"
    assert body["subscription"]["plan_version"] == 2
    assert body["subscription"]["billing_cycle"] == "YEARLY"


def test_admin_commercial_plan_change_denies_read_only_role_with_admin_envelope(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "NEFT_SUPPORT")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/plan",
            json={
                "plan_code": "PREMIUM",
                "plan_version": 2,
                "billing_cycle": "YEARLY",
                "status": "ACTIVE",
                "reason": "upgrade",
            },
        )

    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "admin_forbidden"
    assert body["message"] == "forbidden_admin_role"


def test_admin_commercial_enable_addon_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/addons/enable",
            json={
                "addon_code": "integration.api.webhooks",
                "status": "ACTIVE",
                "reason": "needed",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert any(addon["addon_code"] == "integration.api.webhooks" and addon["status"] == "ACTIVE" for addon in body["addons"])


def test_admin_commercial_disable_addon_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/addons/disable",
            json={
                "addon_code": "integration.helpdesk.zendesk",
                "reason": "cleanup",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert any(addon["addon_code"] == "integration.helpdesk.zendesk" and addon["status"] == "CANCELED" for addon in body["addons"])


def test_admin_commercial_override_upsert_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/overrides",
            json={
                "feature_key": BASELINE_FEATURE_KEY,
                "availability": "ENABLED",
                "limits_json": {"dashboards": 5},
                "reason": "expand",
                "confirm": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert any(
        override["feature_key"] == BASELINE_FEATURE_KEY
        and override["availability"] == "ENABLED"
        and override["limits_json"] == {"dashboards": 5}
        for override in body["overrides"]
    )


def test_admin_commercial_override_upsert_missing_feature_catalog_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
    make_jwt,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_processing_core(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"ATTACH DATABASE ':memory:' AS {DB_SCHEMA}")
        cursor.close()

    tables = _build_commercial_tables(include_feature_catalog=False)
    tables["orgs"].metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(commercial_router, "pg_insert", sqlite_insert)
    monkeypatch.setattr(commercial_router.AuditService, "audit", lambda self, **kwargs: None)
    try:
        with SessionLocal() as db:
            _seed_commercial_state(db, tables)

        headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.post(
                f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/overrides",
                json={
                    "feature_key": BASELINE_FEATURE_KEY,
                    "availability": "ENABLED",
                    "limits_json": {"dashboards": 5},
                    "reason": "expand",
                    "confirm": True,
                },
            )

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["type"] == "http_error"
        assert body["error"]["message"] == "invalid_feature_key"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_admin_commercial_override_remove_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.delete(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/overrides/{BASELINE_FEATURE_KEY}",
            params={"reason": "cleanup"},
        )

    assert response.status_code == 200
    body = response.json()
    assert all(override["feature_key"] != BASELINE_FEATURE_KEY for override in body["overrides"])


def test_admin_commercial_recompute_entitlements_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/entitlements/recompute",
            json={"reason": "refresh"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["hash"]
    assert body["version"] == 3

    with SessionLocal() as db:
        snapshots = db.execute(
            select(tables["org_entitlements_snapshot"].c.version).where(
                tables["org_entitlements_snapshot"].c.org_id == ORG_ID
            )
        ).scalars().all()
        assert sorted(snapshots) == [1, 2, 3]


def test_admin_commercial_update_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/update",
            json={
                "plan": {
                    "plan_code": "PREMIUM",
                    "plan_version": 2,
                    "billing_cycle": "YEARLY",
                    "status": "ACTIVE",
                },
                "reason": "upgrade via aggregate route",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["plan_code"] == "PREMIUM"
    assert body["subscription"]["plan_version"] == 2
    assert body["subscription"]["billing_cycle"] == "YEARLY"

    with SessionLocal() as db:
        subscription = db.execute(
            select(
                tables["org_subscriptions"].c.plan_id,
                tables["org_subscriptions"].c.billing_cycle,
            ).where(tables["org_subscriptions"].c.id == SUBSCRIPTION_ID)
        ).first()
        assert subscription == (PLAN_PREMIUM_ID, "YEARLY")


def test_admin_commercial_update_multi_subupdate_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)
        db.execute(tables["support_plans"].insert().values(id=2, code="STANDARD"))
        db.execute(tables["slo_tiers"].insert().values(id=2, code="PLATINUM"))
        db.commit()

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/update",
            json={
                "plan": {
                    "plan_code": "PREMIUM",
                    "plan_version": 2,
                    "billing_cycle": "YEARLY",
                    "status": "ACTIVE",
                },
                "support_plan": "STANDARD",
                "slo_tier": "PLATINUM",
                "addons": [
                    {
                        "addon_code": "integration.api.webhooks",
                        "status": "ACTIVE",
                        "config_json": {"events": ["orders.updated"]},
                    }
                ],
                "overrides": [
                    {
                        "feature_key": BASELINE_FEATURE_KEY,
                        "availability": "ENABLED",
                        "limits_json": {"dashboards": 6},
                        "reason": "expand",
                        "confirm": True,
                    }
                ],
                "reason": "bulk commercial refresh",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["plan_code"] == "PREMIUM"
    assert body["subscription"]["plan_version"] == 2
    assert body["subscription"]["billing_cycle"] == "YEARLY"
    assert body["subscription"]["support_plan"] == "STANDARD"
    assert body["subscription"]["slo_tier"] == "PLATINUM"
    assert any(
        addon["addon_code"] == "integration.api.webhooks"
        and addon["status"] == "ACTIVE"
        and addon["config_json"] == {"events": ["orders.updated"]}
        for addon in body["addons"]
    )
    assert any(
        override["feature_key"] == BASELINE_FEATURE_KEY
        and override["availability"] == "ENABLED"
        and override["limits_json"] == {"dashboards": 6}
        for override in body["overrides"]
    )

    with SessionLocal() as db:
        subscription = db.execute(
            select(
                tables["org_subscriptions"].c.plan_id,
                tables["org_subscriptions"].c.billing_cycle,
                tables["org_subscriptions"].c.support_plan_id,
                tables["org_subscriptions"].c.slo_tier_id,
            ).where(tables["org_subscriptions"].c.id == SUBSCRIPTION_ID)
        ).first()
        addon_rows = db.execute(
            select(
                tables["org_subscription_addons"].c.addon_id,
                tables["org_subscription_addons"].c.status,
                tables["org_subscription_addons"].c.config_json,
            ).where(tables["org_subscription_addons"].c.org_subscription_id == SUBSCRIPTION_ID)
        ).all()
        override_row = db.execute(
            select(
                tables["org_subscription_overrides"].c.availability,
                tables["org_subscription_overrides"].c.limits_json,
            ).where(
                tables["org_subscription_overrides"].c.org_subscription_id == SUBSCRIPTION_ID,
                tables["org_subscription_overrides"].c.feature_key == BASELINE_FEATURE_KEY,
            )
        ).first()
        assert subscription == (PLAN_PREMIUM_ID, "YEARLY", 2, 2)
        assert (ADDON_WEBHOOKS_ID, "ACTIVE", {"events": ["orders.updated"]}) in addon_rows
        assert override_row == ("ENABLED", {"dashboards": 6})


def test_admin_commercial_update_dry_run_returns_preview_without_persisting(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)
        db.execute(tables["support_plans"].insert().values(id=2, code="STANDARD"))
        db.execute(tables["slo_tiers"].insert().values(id=2, code="PLATINUM"))
        db.commit()

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/update",
            json={
                "plan": {
                    "plan_code": "PREMIUM",
                    "plan_version": 2,
                    "billing_cycle": "YEARLY",
                    "status": "ACTIVE",
                },
                "support_plan": "STANDARD",
                "slo_tier": "PLATINUM",
                "addons": [
                    {
                        "addon_code": "integration.api.webhooks",
                        "status": "ACTIVE",
                        "config_json": {"events": ["orders.updated"]},
                    }
                ],
                "overrides": [
                    {
                        "feature_key": BASELINE_FEATURE_KEY,
                        "availability": "ENABLED",
                        "limits_json": {"dashboards": 6},
                        "reason": "expand",
                        "confirm": True,
                    }
                ],
                "reason": "preview only",
                "dry_run": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["plan_code"] == "PREMIUM"
    assert body["subscription"]["plan_version"] == 2
    assert body["subscription"]["billing_cycle"] == "YEARLY"
    assert body["subscription"]["support_plan"] == "STANDARD"
    assert body["subscription"]["slo_tier"] == "PLATINUM"
    assert any(
        addon["addon_code"] == "integration.api.webhooks"
        and addon["status"] == "ACTIVE"
        and addon["config_json"] == {"events": ["orders.updated"]}
        for addon in body["addons"]
    )
    assert any(
        override["feature_key"] == BASELINE_FEATURE_KEY
        and override["availability"] == "ENABLED"
        and override["limits_json"] == {"dashboards": 6}
        for override in body["overrides"]
    )
    assert body["entitlements_snapshot"]["hash"] == "snapshot-hash-2"

    with SessionLocal() as db:
        subscription = db.execute(
            select(
                tables["org_subscriptions"].c.plan_id,
                tables["org_subscriptions"].c.billing_cycle,
                tables["org_subscriptions"].c.support_plan_id,
                tables["org_subscriptions"].c.slo_tier_id,
            ).where(tables["org_subscriptions"].c.id == SUBSCRIPTION_ID)
        ).first()
        addon_rows = db.execute(
            select(
                tables["org_subscription_addons"].c.addon_id,
                tables["org_subscription_addons"].c.status,
            ).where(tables["org_subscription_addons"].c.org_subscription_id == SUBSCRIPTION_ID)
        ).all()
        override_row = db.execute(
            select(
                tables["org_subscription_overrides"].c.availability,
                tables["org_subscription_overrides"].c.limits_json,
            ).where(
                tables["org_subscription_overrides"].c.org_subscription_id == SUBSCRIPTION_ID,
                tables["org_subscription_overrides"].c.feature_key == BASELINE_FEATURE_KEY,
            )
        ).first()
        snapshots = db.execute(
            select(tables["org_entitlements_snapshot"].c.version).where(
                tables["org_entitlements_snapshot"].c.org_id == ORG_ID
            )
        ).scalars().all()
        assert subscription == (PLAN_BASIC_ID, "MONTHLY", 1, 1)
        assert all(row[0] != ADDON_WEBHOOKS_ID for row in addon_rows)
        assert override_row == ("LIMITED", {"dashboards": 2})
        assert sorted(snapshots) == [1, 2]


def test_admin_commercial_update_mixed_valid_and_invalid_is_atomic(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/update",
            json={
                "plan": {
                    "plan_code": "PREMIUM",
                    "plan_version": 2,
                    "billing_cycle": "YEARLY",
                    "status": "ACTIVE",
                },
                "overrides": [
                    {
                        "feature_key": "feature.unknown",
                        "availability": "ENABLED",
                        "limits_json": {"dashboards": 5},
                        "reason": "invalid feature",
                        "confirm": True,
                    }
                ],
                "reason": "mixed invalid payload",
            },
        )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert body["error"]["message"] == "invalid_feature_key"

    with SessionLocal() as db:
        subscription = db.execute(
            select(
                tables["org_subscriptions"].c.plan_id,
                tables["org_subscriptions"].c.billing_cycle,
            ).where(tables["org_subscriptions"].c.id == SUBSCRIPTION_ID)
        ).first()
        override_row = db.execute(
            select(
                tables["org_subscription_overrides"].c.availability,
                tables["org_subscription_overrides"].c.limits_json,
            ).where(
                tables["org_subscription_overrides"].c.org_subscription_id == SUBSCRIPTION_ID,
                tables["org_subscription_overrides"].c.feature_key == BASELINE_FEATURE_KEY,
            )
        ).first()
        assert subscription == (PLAN_BASIC_ID, "MONTHLY")
        assert override_row == ("LIMITED", {"dashboards": 2})


def test_admin_commercial_update_mixed_supported_and_not_supported_is_atomic(
    monkeypatch: pytest.MonkeyPatch,
    make_jwt,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_processing_core(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"ATTACH DATABASE ':memory:' AS {DB_SCHEMA}")
        cursor.close()

    tables = _build_commercial_tables(include_support_plan_column=False)
    tables["orgs"].metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(commercial_router, "pg_insert", sqlite_insert)
    monkeypatch.setattr(commercial_router.AuditService, "audit", lambda self, **kwargs: None)
    try:
        with SessionLocal() as db:
            _seed_commercial_state(db, tables)

        headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.post(
                f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/update",
                json={
                    "plan": {
                        "plan_code": "PREMIUM",
                        "plan_version": 2,
                        "billing_cycle": "YEARLY",
                        "status": "ACTIVE",
                    },
                    "support_plan": "DEDICATED",
                    "reason": "mixed not-supported payload",
                },
            )

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["type"] == "http_error"
        assert body["error"]["message"] == "support_plan_not_supported"

        with SessionLocal() as db:
            subscription = db.execute(
                select(
                    tables["org_subscriptions"].c.plan_id,
                    tables["org_subscriptions"].c.billing_cycle,
                    tables["org_subscriptions"].c.status,
                ).where(tables["org_subscriptions"].c.id == SUBSCRIPTION_ID)
            ).first()
            assert subscription == (PLAN_BASIC_ID, "MONTHLY", "ACTIVE")
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/update",
            {
                "plan": {
                    "plan_code": "PREMIUM",
                    "plan_version": 2,
                    "billing_cycle": "YEARLY",
                    "status": "ACTIVE",
                },
                "reason": "upgrade",
            },
        ),
        (
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/roles/add",
            {"role": "PARTNER", "reason": "grant"},
        ),
        (
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/roles/remove",
            {"role": "CLIENT", "reason": "revoke"},
        ),
        (
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/status",
            {"status": "SUSPENDED", "reason": "pause"},
        ),
    ],
)
def test_admin_commercial_remaining_write_routes_deny_read_only_role(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
    path: str,
    payload: dict[str, object],
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "NEFT_SUPPORT")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(path, json=payload)

    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "admin_forbidden"
    assert body["message"] == "forbidden_admin_role"



def test_admin_commercial_add_role_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/roles/add",
            json={"role": "PARTNER", "reason": "expand org access"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {"org_id": ORG_ID, "roles": ["CLIENT", "PARTNER"]}

    with SessionLocal() as db:
        stored_roles = db.execute(select(tables["orgs"].c.roles).where(tables["orgs"].c.id == ORG_ID)).scalar_one()
        assert sorted(stored_roles) == ["CLIENT", "PARTNER"]



def test_admin_commercial_remove_role_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)
        db.execute(tables["orgs"].update().where(tables["orgs"].c.id == ORG_ID).values(roles=["CLIENT", "PARTNER"]))
        db.commit()

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/roles/remove",
            json={"role": "PARTNER", "reason": "cleanup org access"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {"org_id": ORG_ID, "roles": ["CLIENT"]}

    with SessionLocal() as db:
        stored_roles = db.execute(select(tables["orgs"].c.roles).where(tables["orgs"].c.id == ORG_ID)).scalar_one()
        assert stored_roles == ["CLIENT"]



def test_admin_commercial_roles_add_without_roles_column_returns_not_supported(
    monkeypatch: pytest.MonkeyPatch,
    make_jwt,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_processing_core(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"ATTACH DATABASE ':memory:' AS {DB_SCHEMA}")
        cursor.close()

    tables = _build_commercial_tables(include_org_roles_column=False)
    tables["orgs"].metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(commercial_router, "pg_insert", sqlite_insert)
    monkeypatch.setattr(commercial_router.AuditService, "audit", lambda self, **kwargs: None)
    try:
        with SessionLocal() as db:
            _seed_commercial_state(db, tables)

        headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.post(
                f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/roles/add",
                json={"role": "PARTNER", "reason": "grant"},
            )

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["type"] == "http_error"
        assert body["error"]["message"] == "org_roles_not_supported"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()



def test_admin_commercial_status_change_happy_path(
    db_session_factory: tuple[sessionmaker[Session], dict[str, Table]],
    make_jwt,
) -> None:
    SessionLocal, tables = db_session_factory
    with SessionLocal() as db:
        _seed_commercial_state(db, tables)

    headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
    with TestClient(app, headers=headers) as api_client:
        response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/status",
            json={"status": "SUSPENDED", "reason": "pause org"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["status"] == "SUSPENDED"

    with SessionLocal() as db:
        stored_status = db.execute(select(tables["org_subscriptions"].c.status).where(tables["org_subscriptions"].c.id == SUBSCRIPTION_ID)).scalar_one()
        assert stored_status == "SUSPENDED"



def test_admin_commercial_update_support_plan_without_column_returns_not_supported(
    monkeypatch: pytest.MonkeyPatch,
    make_jwt,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_processing_core(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"ATTACH DATABASE ':memory:' AS {DB_SCHEMA}")
        cursor.close()

    tables = _build_commercial_tables(include_support_plan_column=False)
    tables["orgs"].metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(commercial_router, "pg_insert", sqlite_insert)
    monkeypatch.setattr(commercial_router.AuditService, "audit", lambda self, **kwargs: None)
    try:
        with SessionLocal() as db:
            _seed_commercial_state(db, tables)

        headers = _admin_headers(make_jwt, "ADMIN", "NEFT_SUPERADMIN")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.post(
                f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/update",
                json={"support_plan": "DEDICATED", "reason": "sync support tier"},
            )

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["type"] == "http_error"
        assert body["error"]["message"] == "support_plan_not_supported"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
