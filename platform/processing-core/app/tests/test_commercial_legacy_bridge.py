from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, Numeric, String, Table, create_engine, event, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.db.schema import DB_SCHEMA
from app.main import app
from app.routers.admin import commercial as commercial_router
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.subscription_billing import update_invoice_status


ORG_ID = 101
LEGACY_SUBSCRIPTION_ID = "legacy-subscription-1"
CLIENT_ID = "00000000-0000-0000-0000-000000000001"
PLAN_FREE_ID = "plan-free"
PLAN_CONTROL_ID = "plan-control"


@pytest.fixture()
def legacy_db(monkeypatch: pytest.MonkeyPatch) -> tuple[sessionmaker[Session], dict[str, Table]]:
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")

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

    metadata = MetaData()
    tables = {
        "orgs": Table(
            "orgs",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String(128), nullable=True),
            Column("status", String(32), nullable=True),
            Column("roles", JSON, nullable=True),
            schema=DB_SCHEMA,
        ),
        "client_subscriptions": Table(
            "client_subscriptions",
            metadata,
            Column("id", String(64), primary_key=True),
            Column("tenant_id", Integer, nullable=False),
            Column("client_id", String(64), nullable=False),
            Column("plan_id", String(64), nullable=False),
            Column("status", String(32), nullable=False),
            Column("start_at", DateTime(timezone=True), nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=True),
            schema=DB_SCHEMA,
        ),
        "subscription_plans": Table(
            "subscription_plans",
            metadata,
            Column("id", String(64), primary_key=True),
            Column("code", String(64), nullable=False),
            Column("title", String(128), nullable=True),
            Column("billing_period_months", Integer, nullable=False),
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
        "billing_invoices": Table(
            "billing_invoices",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("org_id", Integer, nullable=False),
            Column("subscription_id", String(64), nullable=True),
            Column("period_start", String(16), nullable=True),
            Column("period_end", String(16), nullable=True),
            Column("status", String(32), nullable=False),
            Column("total_amount", Numeric(18, 2), nullable=True),
            Column("currency", String(8), nullable=True),
            Column("issued_at", DateTime(timezone=True), nullable=True),
            Column("due_at", DateTime(timezone=True), nullable=True),
            Column("paid_at", DateTime(timezone=True), nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=True),
            schema=DB_SCHEMA,
        ),
    }
    metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    admin_token = {"roles": ["ADMIN", "NEFT_SUPERADMIN"], "role": "NEFT_SUPERADMIN", "user_id": "admin-1"}
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[commercial_router.require_admin_user] = lambda: admin_token
    monkeypatch.setattr(commercial_router, "pg_insert", sqlite_insert)
    monkeypatch.setattr(commercial_router.AuditService, "audit", lambda self, **kwargs: None)

    try:
        yield SessionLocal, tables
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(commercial_router.require_admin_user, None)
        engine.dispose()


def _seed_legacy_state(session: Session, tables: dict[str, Table]) -> None:
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    session.execute(
        tables["orgs"].insert().values(
            id=ORG_ID,
            name="Demo Client",
            status="ACTIVE",
            roles=["CLIENT"],
        )
    )
    session.execute(
        tables["subscription_plans"].insert(),
        [
            {"id": PLAN_FREE_ID, "code": "FREE_BASE", "title": "Free Base", "billing_period_months": 1},
            {"id": PLAN_CONTROL_ID, "code": "CONTROL", "title": "Control", "billing_period_months": 1},
        ],
    )
    session.execute(
        tables["subscription_plan_modules"].insert(),
        [
            {
                "plan_id": PLAN_FREE_ID,
                "module_code": "ANALYTICS",
                "enabled": 1,
                "tier": "basic",
                "limits_json": {"exports_per_month": 1},
            },
            {
                "plan_id": PLAN_FREE_ID,
                "module_code": "DOCS",
                "enabled": 1,
                "tier": "basic",
                "limits_json": {},
            },
            {
                "plan_id": PLAN_CONTROL_ID,
                "module_code": "ANALYTICS",
                "enabled": 1,
                "tier": "control",
                "limits_json": {"exports_per_month": 20},
            },
            {
                "plan_id": PLAN_CONTROL_ID,
                "module_code": "DOCS",
                "enabled": 1,
                "tier": "control",
                "limits_json": {},
            },
            {
                "plan_id": PLAN_CONTROL_ID,
                "module_code": "BILLING",
                "enabled": 1,
                "tier": "control",
                "limits_json": {},
            },
        ],
    )
    session.execute(
        tables["client_subscriptions"].insert().values(
            id=LEGACY_SUBSCRIPTION_ID,
            tenant_id=ORG_ID,
            client_id=CLIENT_ID,
            plan_id=PLAN_FREE_ID,
            status="PAST_DUE",
            start_at=now,
            created_at=now,
        )
    )
    session.execute(
        tables["billing_invoices"].insert().values(
            id=701,
            org_id=ORG_ID,
            subscription_id=LEGACY_SUBSCRIPTION_ID,
            status="ISSUED",
            total_amount=1000,
            currency="RUB",
            created_at=now,
        )
    )
    session.commit()


def test_entitlements_snapshot_uses_legacy_subscription_modules(legacy_db: tuple[sessionmaker[Session], dict[str, Table]]) -> None:
    SessionLocal, tables = legacy_db
    with SessionLocal() as session:
        _seed_legacy_state(session, tables)
        snapshot = get_org_entitlements_snapshot(session, org_id=ORG_ID)

    assert snapshot.hash
    assert snapshot.entitlements["subscription"]["plan_code"] == "FREE_BASE"
    assert snapshot.entitlements["subscription"]["status"] == "OVERDUE"
    assert snapshot.entitlements["features"]["feature.export.async"]["availability"] == "ENABLED"
    assert snapshot.entitlements["modules"]["ANALYTICS"]["enabled"] is True


def test_admin_commercial_legacy_routes_update_client_subscriptions(
    legacy_db: tuple[sessionmaker[Session], dict[str, Table]]
) -> None:
    SessionLocal, tables = legacy_db
    with SessionLocal() as session:
        _seed_legacy_state(session, tables)

    with TestClient(app) as api_client:
        status_response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/status",
            json={"status": "OVERDUE", "reason": "smoke-overdue"},
        )
        assert status_response.status_code == 200
        assert status_response.json()["subscription"]["status"] == "OVERDUE"
        with SessionLocal() as session:
            stored = session.execute(select(tables["client_subscriptions"].c.status)).scalar_one()
            assert stored == "PAST_DUE"

        plan_response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/plan",
            json={
                "plan_code": "CONTROL",
                "plan_version": 1,
                "billing_cycle": "MONTHLY",
                "status": "ACTIVE",
                "reason": "upgrade",
            },
        )
        assert plan_response.status_code == 200
        assert plan_response.json()["subscription"]["plan_code"] == "CONTROL"
        assert plan_response.json()["subscription"]["status"] == "ACTIVE"

        recompute_response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/entitlements/recompute",
            json={"reason": "refresh"},
        )
        assert recompute_response.status_code == 200
        assert recompute_response.json()["hash"]
        assert recompute_response.json()["version"] == 1

    with SessionLocal() as session:
        stored = session.execute(select(tables["client_subscriptions"])).mappings().one()
        assert stored["plan_id"] == PLAN_CONTROL_ID
        assert stored["status"] == "ACTIVE"


def test_admin_commercial_legacy_status_updates_all_runtime_tenant_subscriptions(
    legacy_db: tuple[sessionmaker[Session], dict[str, Table]]
) -> None:
    SessionLocal, tables = legacy_db
    with SessionLocal() as session:
        _seed_legacy_state(session, tables)
        session.execute(
            tables["client_subscriptions"].insert().values(
                id="legacy-subscription-2",
                tenant_id=ORG_ID,
                client_id="00000000-0000-0000-0000-000000000002",
                plan_id=PLAN_FREE_ID,
                status="ACTIVE",
                start_at=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
                created_at=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

    with TestClient(app) as api_client:
        status_response = api_client.post(
            f"/api/core/v1/admin/commercial/orgs/{ORG_ID}/status",
            json={"status": "OVERDUE", "reason": "tenant-overdue"},
        )
        assert status_response.status_code == 200

    with SessionLocal() as session:
        statuses = (
            session.execute(
                select(tables["client_subscriptions"].c.client_id, tables["client_subscriptions"].c.status)
                .where(tables["client_subscriptions"].c.tenant_id == ORG_ID)
                .order_by(tables["client_subscriptions"].c.client_id)
            )
            .mappings()
            .all()
        )

    assert [row["status"] for row in statuses] == ["PAST_DUE", "PAST_DUE"]


def test_update_invoice_status_reactivates_legacy_client_subscription(
    legacy_db: tuple[sessionmaker[Session], dict[str, Table]]
) -> None:
    SessionLocal, tables = legacy_db
    with SessionLocal() as session:
        _seed_legacy_state(session, tables)
        updated = update_invoice_status(session, invoice_id=701, status="PAID", request_ctx=None)
        session.commit()

        assert updated is not None
        assert updated["status"] == "PAID"

        stored = session.execute(select(tables["client_subscriptions"].c.status)).scalar_one()
        assert stored == "ACTIVE"
