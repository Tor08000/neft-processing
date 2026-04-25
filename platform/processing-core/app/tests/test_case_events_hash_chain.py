import base64
import threading
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.cases import Case, CaseEvent, CaseEventType, CaseKind, CasePriority, CaseStatus
from app.routers.admin.cases import router as admin_cases_router
from app.routers.cases import router as cases_router
from app.services.case_event_hashing import canonical_json
from app.services.case_events_service import CaseEventChange, emit_case_event
from app.tests._scoped_router_harness import (
    CASES_TEST_TABLES,
    cases_dependency_overrides,
    require_admin_user_override,
    scoped_session_context,
)


GENESIS_HASH = "GENESIS"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def audit_signing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    monkeypatch.setenv("AUDIT_SIGNING_MODE", "local")
    monkeypatch.setenv("AUDIT_SIGNING_REQUIRED", "true")
    monkeypatch.setenv("AUDIT_SIGNING_ALG", "ed25519")
    monkeypatch.setenv("AUDIT_SIGNING_KEY_ID", "local-test-key")
    monkeypatch.setenv("AUDIT_SIGNING_PRIVATE_KEY_B64", base64.b64encode(private_pem).decode("utf-8"))


@pytest.fixture()
def db_session() -> Session:
    with scoped_session_context(tables=CASES_TEST_TABLES) as session:
        yield session


@pytest.fixture()
def client(db_session: Session):
    app = FastAPI()
    app.include_router(cases_router, prefix="/api/core")
    app.include_router(admin_cases_router, prefix="/api/core/v1/admin")

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    for dependency, override in cases_dependency_overrides().items():
        app.dependency_overrides[dependency] = override
    app.dependency_overrides[require_admin_user] = require_admin_user_override

    with TestClient(app) as test_client:
        yield test_client


def test_canonical_json_is_stable():
    value_a = {"b": 2, "a": 1, "nested": {"y": 2, "x": 1}}
    value_b = {"nested": {"x": 1, "y": 2}, "a": 1, "b": 2}
    assert canonical_json(value_a) == canonical_json(value_b)


def test_case_event_chain_and_verify(make_jwt, client: TestClient, db_session: Session):
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

    close_resp = client.post(
        f"/api/core/v1/admin/cases/{case_id}/close",
        headers=_auth_headers(token),
        json={"resolution_note": "Closed after review"},
    )
    assert close_resp.status_code == 200

    events = (
        db_session.query(CaseEvent)
        .filter(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.seq.asc())
        .all()
    )
    assert [event.seq for event in events] == [1, 2, 3]
    assert events[0].prev_hash == GENESIS_HASH
    assert events[1].prev_hash == events[0].hash
    assert events[2].prev_hash == events[1].hash

    verify_resp = client.post(f"/api/core/v1/admin/cases/{case_id}/events/verify", headers=_auth_headers(token))
    assert verify_resp.status_code == 200
    verify_body = verify_resp.json()
    assert verify_body["chain"]["status"] == "verified"
    assert verify_body["signatures"]["status"] == "verified"

    events[1].payload_redacted = {"tampered": True}
    db_session.commit()

    verify_resp = client.post(f"/api/core/v1/admin/cases/{case_id}/events/verify", headers=_auth_headers(token))
    assert verify_resp.status_code == 200
    body = verify_resp.json()
    assert body["chain"]["status"] == "broken"
    assert body["chain"]["broken_index"] == 1
    assert body["signatures"]["status"] == "verified"


def test_concurrent_emits_keep_sequence(tmp_path):
    db_path = tmp_path / "case_events.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Case.__table__.create(bind=engine)
    CaseEvent.__table__.create(bind=engine)

    session = SessionLocal()
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
    session.add(case)
    session.commit()
    session.close()

    barrier = threading.Barrier(2)

    def _emit():
        db = SessionLocal()
        barrier.wait()
        emit_case_event(
            db,
            case_id=case_id,
            event_type=CaseEventType.STATUS_CHANGED,
            actor=None,
            request_id=None,
            trace_id=None,
            changes=[CaseEventChange(field="status", before="TRIAGE", after="IN_PROGRESS")],
        )
        db.commit()
        db.close()

    thread_a = threading.Thread(target=_emit)
    thread_b = threading.Thread(target=_emit)
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    check_session = SessionLocal()
    events = (
        check_session.query(CaseEvent)
        .filter(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.seq.asc())
        .all()
    )
    check_session.close()

    assert [event.seq for event in events] == [1, 2]
    assert events[1].prev_hash == events[0].hash

    CaseEvent.__table__.drop(bind=engine)
    Case.__table__.drop(bind=engine)
    engine.dispose()
