from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models.case_exports import CaseExport
from app.models.cases import Case, CaseEvent, CaseEventType, CaseKind
from app.models.decision_memory import DecisionMemoryRecord
from app.models.fleet import ClientEmployee, FuelCardGroupMember, FuelGroupAccess
from app.models.fuel import (
    FuelCard,
    FuelCardGroup,
    FuelLimit,
    FuelNetwork,
    FuelStation,
    FuelTransaction,
)
from app.services.case_events_service import verify_case_event_chain, verify_case_event_signatures


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _StubExportStorage:
    def put_bytes(self, key: str, content: bytes, *, content_type: str) -> None:
        return None

    def delete(self, key: str) -> None:
        return None

    def presign_get(self, key: str, *, ttl_seconds: int) -> str:
        return f"https://exports.local/{key}"


@pytest.fixture()
def signing_key() -> bytes:
    private_key = Ed25519PrivateKey.generate()
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture(autouse=True)
def audit_signing_env(monkeypatch: pytest.MonkeyPatch, signing_key: bytes) -> None:
    monkeypatch.setenv("AUDIT_SIGNING_MODE", "local")
    monkeypatch.setenv("AUDIT_SIGNING_REQUIRED", "true")
    monkeypatch.setenv("AUDIT_SIGNING_ALG", "ed25519")
    monkeypatch.setenv("AUDIT_SIGNING_KEY_ID", "local-test-key")
    monkeypatch.setenv("AUDIT_SIGNING_PRIVATE_KEY_B64", base64.b64encode(signing_key).decode("utf-8"))


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Case.__table__.create(bind=engine)
    CaseEvent.__table__.create(bind=engine)
    DecisionMemoryRecord.__table__.create(bind=engine)
    CaseExport.__table__.create(bind=engine)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    FuelCardGroup.__table__.create(bind=engine)
    FuelCard.__table__.create(bind=engine)
    FuelCardGroupMember.__table__.create(bind=engine)
    ClientEmployee.__table__.create(bind=engine)
    FuelGroupAccess.__table__.create(bind=engine)
    FuelLimit.__table__.create(bind=engine)
    FuelTransaction.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        FuelTransaction.__table__.drop(bind=engine)
        FuelLimit.__table__.drop(bind=engine)
        FuelGroupAccess.__table__.drop(bind=engine)
        ClientEmployee.__table__.drop(bind=engine)
        FuelCardGroupMember.__table__.drop(bind=engine)
        FuelCard.__table__.drop(bind=engine)
        FuelCardGroup.__table__.drop(bind=engine)
        FuelStation.__table__.drop(bind=engine)
        FuelNetwork.__table__.drop(bind=engine)
        CaseExport.__table__.drop(bind=engine)
        DecisionMemoryRecord.__table__.drop(bind=engine)
        CaseEvent.__table__.drop(bind=engine)
        Case.__table__.drop(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    monkeypatch.setattr("app.services.case_export_service.ExportStorage", _StubExportStorage)
    monkeypatch.setattr("app.services.export_storage.ExportStorage", _StubExportStorage)
    monkeypatch.setattr("app.services.fleet_service.ExportStorage", _StubExportStorage)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def test_fleet_v1_flow(make_jwt, client: TestClient, db_session: Session) -> None:
    client_id = str(uuid4())
    admin_user_id = str(uuid4())
    admin_token = make_jwt(
        roles=("CLIENT_ADMIN",),
        client_id=client_id,
        sub=admin_user_id,
        extra={"user_id": admin_user_id, "email": "admin@fleet.test", "tenant_id": 1},
    )

    card_payload = {"card_alias": "NEFT-00001234", "masked_pan": "****1111", "currency": "RUB"}
    card_resp = client.post("/api/client/fleet/cards", json=card_payload, headers=_auth_headers(admin_token))
    assert card_resp.status_code == 201
    card_id = card_resp.json()["id"]

    group_resp = client.post(
        "/api/client/fleet/groups",
        json={"name": "Ops", "description": "Ops group"},
        headers=_auth_headers(admin_token),
    )
    assert group_resp.status_code == 201
    group_id = group_resp.json()["id"]

    add_resp = client.post(
        f"/api/client/fleet/groups/{group_id}/members/add",
        json={"card_id": card_id},
        headers=_auth_headers(admin_token),
    )
    assert add_resp.status_code == 200

    invite_resp = client.post(
        "/api/client/fleet/employees/invite",
        json={"email": "viewer@fleet.test"},
        headers=_auth_headers(admin_token),
    )
    assert invite_resp.status_code == 201
    viewer_id = invite_resp.json()["id"]

    grant_resp = client.post(
        f"/api/client/fleet/groups/{group_id}/access/grant",
        json={"employee_id": viewer_id, "role": "viewer"},
        headers=_auth_headers(admin_token),
    )
    assert grant_resp.status_code == 200

    viewer_token = make_jwt(
        roles=("CLIENT_USER",),
        client_id=client_id,
        sub=viewer_id,
        extra={"user_id": viewer_id, "email": "viewer@fleet.test", "tenant_id": 1},
    )
    list_cards = client.get("/api/client/fleet/cards", headers=_auth_headers(viewer_token))
    assert list_cards.status_code == 200
    assert len(list_cards.json()["items"]) == 1

    limit_resp = client.post(
        "/api/client/fleet/limits/set",
        json={
            "scope_type": "CARD_GROUP",
            "scope_id": group_id,
            "period": "DAILY",
            "amount_limit": "1000",
        },
        headers=_auth_headers(viewer_token),
    )
    assert limit_resp.status_code == 403

    manager_resp = client.post(
        "/api/client/fleet/employees/invite",
        json={"email": "manager@fleet.test"},
        headers=_auth_headers(admin_token),
    )
    manager_id = manager_resp.json()["id"]
    grant_manager = client.post(
        f"/api/client/fleet/groups/{group_id}/access/grant",
        json={"employee_id": manager_id, "role": "manager"},
        headers=_auth_headers(admin_token),
    )
    assert grant_manager.status_code == 200

    manager_token = make_jwt(
        roles=("CLIENT_USER",),
        client_id=client_id,
        sub=manager_id,
        extra={"user_id": manager_id, "email": "manager@fleet.test", "tenant_id": 1},
    )
    limit_resp = client.post(
        "/api/client/fleet/limits/set",
        json={
            "scope_type": "CARD_GROUP",
            "scope_id": group_id,
            "period": "DAILY",
            "amount_limit": "1000",
        },
        headers=_auth_headers(manager_token),
    )
    assert limit_resp.status_code == 200

    revoke_resp = client.post(
        f"/api/client/fleet/groups/{group_id}/access/revoke",
        json={"employee_id": viewer_id},
        headers=_auth_headers(admin_token),
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["revoked_at"] is not None

    internal_token = make_jwt(roles=("ADMIN",), sub=str(uuid4()), extra={"tenant_id": 1})
    ingest_payload = {
        "items": [
            {
                "card_id": card_id,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "amount": "100.00",
                "currency": "RUB",
                "external_ref": "ext-1",
            }
        ]
    }
    ingest_resp = client.post(
        "/api/internal/fleet/transactions/ingest",
        json=ingest_payload,
        headers=_auth_headers(internal_token),
    )
    assert ingest_resp.status_code == 200
    assert len(ingest_resp.json()["items"]) == 1

    ingest_again = client.post(
        "/api/internal/fleet/transactions/ingest",
        json=ingest_payload,
        headers=_auth_headers(internal_token),
    )
    assert ingest_again.status_code == 200
    assert len(ingest_again.json()["items"]) == 0

    summary_resp = client.get(
        "/api/client/fleet/spend/summary",
        params={"group_by": "day", "group_id": group_id},
        headers=_auth_headers(admin_token),
    )
    assert summary_resp.status_code == 200
    rows = summary_resp.json()["rows"]
    assert rows
    assert rows[0]["amount"] == "100.00"

    export_resp = client.get(
        "/api/client/fleet/transactions/export",
        params={"group_id": group_id},
        headers=_auth_headers(admin_token),
    )
    assert export_resp.status_code == 200
    assert export_resp.json()["url"].startswith("https://exports.local/")

    case = db_session.query(Case).filter(Case.kind == CaseKind.FLEET).one()
    chain = verify_case_event_chain(db_session, case_id=str(case.id))
    signatures = verify_case_event_signatures(db_session, case_id=str(case.id))
    assert chain.verified is True
    assert signatures.verified is True
