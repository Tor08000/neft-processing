from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, DateTime, Integer, JSON, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.client_limit_change_requests import ClientLimitChangeRequest
from app.models.client_user_roles import ClientUserRole
from app.models.client_users import ClientUser
from app.models.fuel import FleetOfflineProfile


def _client_headers(make_jwt, *, client_id: str, tenant_id: int, roles: tuple[str, ...], sub: str) -> dict[str, str]:
    token = make_jwt(
        roles=roles,
        client_id=client_id,
        sub=sub,
        extra={"tenant_id": tenant_id, "aud": "neft-client", "user_id": sub},
    )
    return {"Authorization": f"Bearer {token}"}


def _build_entitlement_tables() -> dict[str, Table]:
    metadata = MetaData()
    return {
        "org_subscriptions": Table(
            "org_subscriptions",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("org_id", Integer, nullable=False),
            Column("plan_id", String(64), nullable=False),
            Column("status", String(32), nullable=False),
            Column("billing_cycle", String(32), nullable=True),
            Column("support_plan_id", Integer, nullable=True),
            Column("slo_tier_id", Integer, nullable=True),
        ),
        "subscription_plans": Table(
            "subscription_plans",
            metadata,
            Column("id", String(64), primary_key=True),
            Column("code", String(32), nullable=False),
            Column("version", Integer, nullable=True),
        ),
        "subscription_plan_features": Table(
            "subscription_plan_features",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("plan_id", String(64), nullable=False),
            Column("feature_key", String(128), nullable=False),
            Column("availability", String(32), nullable=False),
            Column("limits_json", JSON, nullable=True),
        ),
        "subscription_plan_modules": Table(
            "subscription_plan_modules",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("plan_id", String(64), nullable=False),
            Column("module_code", String(64), nullable=False),
            Column("enabled", Integer, nullable=False, default=1),
            Column("tier", String(32), nullable=True),
            Column("limits_json", JSON, nullable=True),
        ),
        "org_subscription_addons": Table(
            "org_subscription_addons",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("org_subscription_id", Integer, nullable=False),
            Column("addon_id", Integer, nullable=False),
            Column("status", String(32), nullable=False),
        ),
        "addons": Table(
            "addons",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("code", String(128), nullable=False),
        ),
        "org_subscription_overrides": Table(
            "org_subscription_overrides",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("org_subscription_id", Integer, nullable=False),
            Column("feature_key", String(128), nullable=False),
            Column("availability", String(32), nullable=False),
            Column("limits_json", JSON, nullable=True),
        ),
        "support_plans": Table(
            "support_plans",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("code", String(64), nullable=False),
        ),
        "slo_tiers": Table(
            "slo_tiers",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("code", String(64), nullable=False),
        ),
        "org_entitlements_snapshot": Table(
            "org_entitlements_snapshot",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("org_id", Integer, nullable=False),
            Column("subscription_id", Integer, nullable=True),
            Column("entitlements_json", JSON, nullable=False),
            Column("hash", String(128), nullable=False),
            Column("version", Integer, nullable=False),
            Column("computed_at", DateTime(timezone=True), nullable=False),
        ),
    }


def _build_session_factory() -> tuple[sessionmaker[Session], dict[str, Table], object]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(
        bind=engine,
        tables=[
            FleetOfflineProfile.__table__,
            Client.__table__,
            ClientUser.__table__,
            ClientUserRole.__table__,
            AuditLog.__table__,
            ClientLimitChangeRequest.__table__,
        ],
    )
    entitlement_tables = _build_entitlement_tables()
    entitlement_tables["org_subscriptions"].metadata.create_all(bind=engine)

    testing_session_local = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return testing_session_local, entitlement_tables, engine


def _seed_portal_write_entitlements(db: Session, entitlement_tables: dict[str, Table], *, org_id: int) -> None:
    plan_id = "plan-controls-write"
    db.execute(entitlement_tables["subscription_plans"].insert().values(id=plan_id, code="CLIENT_CONTROLS", version=1))
    db.execute(
        entitlement_tables["org_subscriptions"].insert().values(
            org_id=org_id,
            plan_id=plan_id,
            status="ACTIVE",
            billing_cycle="MONTHLY",
            support_plan_id=None,
            slo_tier_id=None,
        )
    )
    db.execute(
        entitlement_tables["subscription_plan_features"].insert(),
        [
            {"plan_id": plan_id, "feature_key": "feature.portal.core", "availability": "ENABLED", "limits_json": None},
            {"plan_id": plan_id, "feature_key": "feature.portal.entities", "availability": "ENABLED", "limits_json": None},
        ],
    )
    db.commit()


@pytest.fixture(autouse=True)
def _allow_mock_providers_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")


def test_limit_change_request_persists_and_emits_audit(make_jwt) -> None:
    SessionLocal, entitlement_tables, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    tenant_id = 7
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls", status="ACTIVE"))
            db.commit()
            _seed_portal_write_entitlements(db, entitlement_tables, org_id=tenant_id)

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id, roles=("CLIENT_ADMIN",), sub="admin-1")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.post(
                "/api/core/client/limits/requests",
                json={"limit_type": "DAILY_AMOUNT", "new_value": 7500, "comment": "Need more headroom"},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "PENDING"
        assert body["request_id"]
        request_id = body["request_id"]

        with SessionLocal() as db:
            item = db.query(ClientLimitChangeRequest).filter(ClientLimitChangeRequest.id == request_id).one()
            assert item.client_id == client_id
            assert item.limit_type == "DAILY_AMOUNT"
            assert item.new_value == Decimal("7500")
            assert item.comment == "Need more headroom"
            assert item.status == "PENDING"
            assert item.created_by == "admin-1"
            assert item.created_at is not None

            audit_entry = (
                db.query(AuditLog)
                .filter(AuditLog.entity_id == request_id)
                .filter(AuditLog.event_type == "limit_change_request")
                .one()
            )
            assert audit_entry.action == "create_limit_request"
            assert audit_entry.after["limit_type"] == "DAILY_AMOUNT"
            assert audit_entry.after["new_value"] == 7500
            assert audit_entry.after["status"] == "PENDING"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_limit_change_request_is_forbidden_for_non_admin(make_jwt) -> None:
    SessionLocal, _, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls", status="ACTIVE"))
            db.commit()

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=1, roles=("CLIENT_USER",), sub="user-1")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.post(
                "/api/core/client/limits/requests",
                json={"limit_type": "DAILY_AMOUNT", "new_value": 7500},
            )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_disable_user_marks_membership_disabled_and_emits_audit(make_jwt) -> None:
    SessionLocal, entitlement_tables, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    tenant_id = 1
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls", status="ACTIVE"))
            db.add(ClientUser(client_id=client_id, user_id="user-2", status="ACTIVE"))
            db.add(ClientUserRole(client_id=client_id, user_id="user-2", roles=["CLIENT_MANAGER"]))
            db.commit()
            _seed_portal_write_entitlements(db, entitlement_tables, org_id=tenant_id)

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id, roles=("CLIENT_ADMIN",), sub="admin-1")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.delete("/api/core/client/users/user-2")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "user_id": "user-2", "disabled": True}

        with SessionLocal() as db:
            record = (
                db.query(ClientUser)
                .filter(ClientUser.client_id == client_id, ClientUser.user_id == "user-2")
                .one()
            )
            assert record.status == "DISABLED"

            audit_entry = (
                db.query(AuditLog)
                .filter(AuditLog.entity_id == "user-2")
                .filter(AuditLog.event_type == "user_disable")
                .order_by(AuditLog.ts.desc())
                .first()
            )
            assert audit_entry is not None
            assert audit_entry.action == "disable_user"
            assert audit_entry.before["status"] == "ACTIVE"
            assert audit_entry.after["status"] == "DISABLED"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_disable_user_blocks_self_disable(make_jwt) -> None:
    SessionLocal, entitlement_tables, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    tenant_id = 1
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls", status="ACTIVE"))
            db.add(ClientUser(client_id=client_id, user_id="user-1", status="ACTIVE"))
            db.add(ClientUserRole(client_id=client_id, user_id="user-1", roles=["CLIENT_ADMIN"]))
            db.commit()
            _seed_portal_write_entitlements(db, entitlement_tables, org_id=tenant_id)

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id, roles=("CLIENT_ADMIN",), sub="user-1")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.delete("/api/core/client/users/user-1")

        assert response.status_code == 400
        assert response.json()["error"]["message"] == "cannot_disable_self"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_disable_user_blocks_last_owner(make_jwt) -> None:
    SessionLocal, entitlement_tables, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    tenant_id = 1
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls", status="ACTIVE"))
            db.add(ClientUser(client_id=client_id, user_id="owner-1", status="ACTIVE"))
            db.add(ClientUserRole(client_id=client_id, user_id="owner-1", roles=["CLIENT_OWNER"]))
            db.commit()
            _seed_portal_write_entitlements(db, entitlement_tables, org_id=tenant_id)

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id, roles=("CLIENT_ADMIN",), sub="admin-1")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.delete("/api/core/client/users/owner-1")

        assert response.status_code == 409
        assert response.json()["error"]["message"] == "cannot_disable_last_owner"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_disable_user_is_idempotent_for_already_disabled(make_jwt) -> None:
    SessionLocal, entitlement_tables, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    tenant_id = 1
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls", status="ACTIVE"))
            db.add(ClientUser(client_id=client_id, user_id="user-2", status="DISABLED"))
            db.add(ClientUserRole(client_id=client_id, user_id="user-2", roles=["CLIENT_MANAGER"]))
            db.commit()
            _seed_portal_write_entitlements(db, entitlement_tables, org_id=tenant_id)

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id, roles=("CLIENT_ADMIN",), sub="admin-1")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.delete("/api/core/client/users/user-2")

        assert response.status_code == 200
        with SessionLocal() as db:
            record = (
                db.query(ClientUser)
                .filter(ClientUser.client_id == client_id, ClientUser.user_id == "user-2")
                .one()
            )
            assert record.status == "DISABLED"
            audit_entry = (
                db.query(AuditLog)
                .filter(AuditLog.entity_id == "user-2")
                .filter(AuditLog.event_type == "user_disable")
                .order_by(AuditLog.ts.desc())
                .first()
            )
            assert audit_entry is not None
            assert audit_entry.reason == "already_disabled"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_disable_user_is_forbidden_for_non_admin(make_jwt) -> None:
    SessionLocal, _, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls", status="ACTIVE"))
            db.add(ClientUser(client_id=client_id, user_id="user-2", status="ACTIVE"))
            db.commit()

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=1, roles=("CLIENT_USER",), sub="user-1")
        with TestClient(app, headers=headers) as api_client:
            response = api_client.delete("/api/core/client/users/user-2")

        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
