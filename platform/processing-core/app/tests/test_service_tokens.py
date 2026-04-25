from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.service_identities import (
    ServiceIdentity,
    ServiceToken,
    ServiceTokenAudit,
    ServiceTokenAuditAction,
    ServiceTokenStatus,
)
from app.models.abac import AbacPolicy, AbacPolicyEffect, AbacPolicyVersion, AbacPolicyVersionStatus
from app.routers.admin.security import router as admin_security_router
from app.routers.internal.security import router as internal_security_router

from ._scoped_router_harness import scoped_session_context


SERVICE_TOKEN_TEST_TABLES = (
    ServiceIdentity.__table__,
    ServiceToken.__table__,
    ServiceTokenAudit.__table__,
    AbacPolicyVersion.__table__,
    AbacPolicy.__table__,
)

def _admin_user_override() -> dict[str, str]:
    return {"user_id": "admin-1", "sub": "admin-1"}


@pytest.fixture
def db_session():
    with scoped_session_context(tables=SERVICE_TOKEN_TEST_TABLES) as session:
        yield session


@pytest.fixture
def security_client_factory(db_session):
    def _factory(*, headers: dict[str, str] | None = None) -> TestClient:
        app = FastAPI()
        app.include_router(admin_security_router, prefix="/api/v1/admin")
        app.include_router(internal_security_router)

        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        app.dependency_overrides[require_admin_user] = _admin_user_override
        app.dependency_overrides[get_db] = override_get_db
        return TestClient(app, headers=headers or {})

    return _factory


def _create_identity(api_client):
    response = api_client.post(
        "/api/v1/admin/security/service-identities",
        json={"service_name": "document-service", "description": "Docs"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _issue_token(api_client, identity_id, scopes):
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    response = api_client.post(
        f"/api/v1/admin/security/service-identities/{identity_id}/tokens/issue",
        json={"scopes": scopes, "expires_at": expires_at.isoformat(), "env": "test"},
    )
    assert response.status_code == 200
    return response.json()


def _seed_abac_allow(session):
    version = AbacPolicyVersion(
        name="service",
        status=AbacPolicyVersionStatus.ACTIVE,
        activated_at=datetime.now(timezone.utc),
    )
    session.add(version)
    session.flush()
    session.add(
        AbacPolicy(
            version_id=version.id,
            code="service_ping_allow",
            effect=AbacPolicyEffect.ALLOW,
            priority=100,
            actions=["rules:evaluate"],
            resource_type="SYSTEM",
            condition={"eq": ["principal.type", "SERVICE"]},
            reason_code="SERVICE_ALLOWED",
        )
    )
    session.commit()


def test_issue_token_and_use_scope(db_session, admin_auth_headers, security_client_factory):
    _seed_abac_allow(db_session)
    with security_client_factory(headers=admin_auth_headers) as api_client:
        identity_id = _create_identity(api_client)
        issued = _issue_token(api_client, identity_id, ["rules:evaluate"])

    token_value = issued["token"]
    with security_client_factory(headers={"Authorization": f"Bearer {token_value}"}) as service_client:
        response = service_client.get("/api/internal/security/ping")
        assert response.status_code == 200
        assert response.json()["service"] == "document-service"

    audit_actions = {row.action for row in db_session.query(ServiceTokenAudit).all()}
    assert ServiceTokenAuditAction.ISSUED in audit_actions
    assert ServiceTokenAuditAction.USED in audit_actions

    token_record = db_session.query(ServiceToken).filter(ServiceToken.id == issued["token_id"]).one()
    assert token_record.token_hash != token_value


def test_missing_scope_denied_and_audited(db_session, admin_auth_headers, security_client_factory):
    _seed_abac_allow(db_session)
    with security_client_factory(headers=admin_auth_headers) as api_client:
        identity_id = _create_identity(api_client)
        issued = _issue_token(api_client, identity_id, ["documents:read"])

    token_value = issued["token"]
    with security_client_factory(headers={"Authorization": f"Bearer {token_value}"}) as service_client:
        response = service_client.get("/api/internal/security/ping")
        assert response.status_code == 403

    denied = (
        db_session.query(ServiceTokenAudit)
        .filter(ServiceTokenAudit.action == ServiceTokenAuditAction.DENIED)
        .count()
    )
    assert denied == 1


def test_rotate_grace_and_revoke(db_session, admin_auth_headers, security_client_factory):
    _seed_abac_allow(db_session)
    with security_client_factory(headers=admin_auth_headers) as api_client:
        identity_id = _create_identity(api_client)
        issued = _issue_token(api_client, identity_id, ["rules:evaluate"])
        rotate_resp = api_client.post(
            f"/api/v1/admin/security/service-tokens/{issued['token_id']}/rotate",
            json={"grace_hours": 1, "env": "test"},
        )
        assert rotate_resp.status_code == 200
        rotated = rotate_resp.json()

    old_token = issued["token"]
    with security_client_factory(headers={"Authorization": f"Bearer {old_token}"}) as service_client:
        response = service_client.get("/api/internal/security/ping")
        assert response.status_code == 200

    record = db_session.query(ServiceToken).filter(ServiceToken.id == issued["token_id"]).one()
    record.rotation_grace_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    with security_client_factory(headers={"Authorization": f"Bearer {old_token}"}) as service_client:
        response = service_client.get("/api/internal/security/ping")
        assert response.status_code == 401

    with security_client_factory(headers=admin_auth_headers) as api_client:
        revoke_resp = api_client.post(
            f"/api/v1/admin/security/service-tokens/{rotated['token_id']}/revoke",
            json={},
        )
        assert revoke_resp.status_code == 200

    new_token = rotated["token"]
    with security_client_factory(headers={"Authorization": f"Bearer {new_token}"}) as service_client:
        response = service_client.get("/api/internal/security/ping")
        assert response.status_code == 401

    revoked = db_session.query(ServiceToken).filter(ServiceToken.id == rotated["token_id"]).one()
    assert revoked.status == ServiceTokenStatus.REVOKED
