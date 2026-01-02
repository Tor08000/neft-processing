import base64
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
from app.models.cases import Case, CaseComment, CaseEvent, CaseEventType, CaseKind, CasePriority, CaseSnapshot, CaseStatus
from app.services.audit_signing import AuditSigningError, LocalSigner
from app.services.case_events_service import CaseEventChange, emit_case_event


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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
    CaseSnapshot.__table__.create(bind=engine)
    CaseComment.__table__.create(bind=engine)
    CaseEvent.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        CaseEvent.__table__.drop(bind=engine)
        CaseComment.__table__.drop(bind=engine)
        CaseSnapshot.__table__.drop(bind=engine)
        Case.__table__.drop(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def test_local_signer_signs_and_verifies(signing_key: bytes) -> None:
    signer = LocalSigner(alg="ed25519", key_id="local-test-key", private_key_pem=signing_key)
    message = b"audit-signature"
    signature = signer.sign(message)
    assert signer.verify(message, signature) is True


def test_case_event_signature_verification(make_jwt, client: TestClient, db_session: Session) -> None:
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1, "email": "admin@neft.io"})
    payload = {
        "kind": "operation",
        "entity_id": "op-123",
        "priority": "MEDIUM",
        "note": "call me +7 999 123 45 12",
        "explain": {"decision": "DECLINE", "score": 82},
        "diff": {"score_diff": {"risk_before": 0.82, "risk_after": 0.47}},
        "selected_actions": [{"code": "REQUEST_DOCS", "what_if": {"impact": 0.1}}],
    }

    resp = client.post("/api/core/cases", headers=_auth_headers(token), json=payload)
    assert resp.status_code == 201
    case_id = resp.json()["id"]

    status_resp = client.post(
        f"/api/core/v1/admin/cases/{case_id}/status",
        headers=_auth_headers(token),
        json={"status": "IN_PROGRESS"},
    )
    assert status_resp.status_code == 200

    event = (
        db_session.query(CaseEvent)
        .filter(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.seq.asc())
        .first()
    )
    assert event is not None
    assert event.signature is not None
    assert event.signature_alg == "ed25519"
    assert event.signing_key_id == "local-test-key"
    assert event.signed_at is not None

    verify_resp = client.post(f"/api/core/v1/admin/cases/{case_id}/events/verify", headers=_auth_headers(token))
    assert verify_resp.status_code == 200
    verify_body = verify_resp.json()
    assert verify_body["chain"]["status"] == "verified"
    assert verify_body["signatures"]["status"] == "verified"

    event.signature = "invalid"
    db_session.commit()

    verify_resp = client.post(f"/api/core/v1/admin/cases/{case_id}/events/verify", headers=_auth_headers(token))
    assert verify_resp.status_code == 200
    verify_body = verify_resp.json()
    assert verify_body["chain"]["status"] == "verified"
    assert verify_body["signatures"]["status"] == "broken"
    assert verify_body["signatures"]["broken_index"] == 0
    assert verify_body["signatures"]["key_id"] == "local-test-key"


def test_emit_event_fails_without_signature(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    monkeypatch.setenv("AUDIT_SIGNING_PRIVATE_KEY_B64", "")
    monkeypatch.setenv("AUDIT_SIGNING_REQUIRED", "true")
    case_id = str(uuid4())
    case = Case(
        id=case_id,
        tenant_id=1,
        kind=CaseKind.OPERATION,
        entity_id="op-1",
        title="case",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
    )
    db_session.add(case)
    db_session.commit()

    with pytest.raises(AuditSigningError):
        emit_case_event(
            db_session,
            case_id=case_id,
            event_type=CaseEventType.STATUS_CHANGED,
            actor=None,
            request_id=None,
            trace_id=None,
            changes=[CaseEventChange(field="status", before="TRIAGE", after="IN_PROGRESS")],
        )
