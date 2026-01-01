import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models.cases import Case, CaseComment, CaseEvent, CaseEventType, CaseKind, CasePriority, CaseSnapshot, CaseStatus
from app.services.case_event_hashing import canonical_json
from app.services.case_events_service import CaseEventChange, emit_case_event


GENESIS_HASH = "GENESIS"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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
    assert verify_resp.json()["verified"] is True

    events[1].payload_redacted = {"tampered": True}
    db_session.commit()

    verify_resp = client.post(f"/api/core/v1/admin/cases/{case_id}/events/verify", headers=_auth_headers(token))
    assert verify_resp.status_code == 200
    body = verify_resp.json()
    assert body["verified"] is False
    assert body["broken_index"] == 1


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
