from __future__ import annotations

import base64
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as app_main
from app.db import get_db
from app.main import app
from app.models.case_exports import CaseExport
from app.models.cases import Case, CaseComment, CaseEvent, CaseKind, CasePriority, CaseSnapshot, CaseStatus
from app.models.decision_memory import DecisionMemoryRecord
from app.services.case_events_service import CaseEventActor
from app.services.case_export_service import create_export
from app.services.cases_service import close_case, create_case


class FakeExportStorage:
    objects: dict[str, tuple[bytes, str]] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    def put_bytes(self, key: str, content: bytes, *, content_type: str, retain_until=None) -> None:
        self.objects[key] = (content, content_type)

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def presign_get(self, key: str, *, ttl_seconds: int) -> str:
        return f"https://exports.local/{key}?ttl={ttl_seconds}"

    def head(self, key: str) -> dict | None:
        if key not in self.objects:
            return None
        content, _ = self.objects[key]
        return {"ContentLength": len(content)}

    def get_bytes(self, key: str) -> bytes:
        content, _ = self.objects.get(key, (b"", ""))
        return content


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
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    monkeypatch.setattr(app_main.settings, "APP_ENV", "dev", raising=False)
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
    CaseExport.__table__.create(bind=engine)
    DecisionMemoryRecord.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        DecisionMemoryRecord.__table__.drop(bind=engine)
        CaseExport.__table__.drop(bind=engine)
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


def test_decision_memory_records_case_and_close(db_session: Session) -> None:
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    mastery_snapshot = {"level": "operator", "progress_to_next": 0.2}
    actor_id = str(uuid4())
    case = create_case(
        db_session,
        tenant_id=1,
        kind=CaseKind.OPERATION,
        entity_type=None,
        entity_id="op-1",
        kpi_key=None,
        window_days=None,
        title=None,
        description=None,
        priority=CasePriority.MEDIUM,
        note="Created from explain",
        explain={"decision": "DECLINE", "score": 0.8},
        diff={"score_diff": {"risk_before": 0.9, "risk_after": 0.7}},
        selected_actions=None,
        mastery_snapshot=mastery_snapshot,
        created_by=actor_id,
        request_id="req-1",
        trace_id="trace-1",
    )
    db_session.commit()

    records = db_session.query(DecisionMemoryRecord).filter(DecisionMemoryRecord.case_id == case.id).all()
    decision_types = {record.decision_type for record in records}
    assert {"action", "explain", "diff"}.issubset(decision_types)
    for record in records:
        assert record.audit_event_id is not None
        assert record.context_snapshot is not None
        assert record.mastery_snapshot == mastery_snapshot

    close_case(
        db_session,
        case=case,
        actor=actor_id,
        resolution_note="Resolved",
        score_snapshot={"score": 0.2},
        mastery_snapshot=mastery_snapshot,
        now=now,
    )
    db_session.commit()
    close_record = (
        db_session.query(DecisionMemoryRecord)
        .filter(DecisionMemoryRecord.case_id == case.id, DecisionMemoryRecord.decision_type == "close")
        .one()
    )
    assert close_record.rationale == "Resolved"
    assert close_record.score_snapshot == {"score": 0.2}


def test_decision_memory_records_export(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.case_export_service.ExportStorage", FakeExportStorage)
    actor_id = str(uuid4())
    case = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.OPERATION,
        title="case",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
    )
    db_session.add(case)
    db_session.commit()

    export = create_export(
        db_session,
        kind="EXPLAIN",
        case_id=case.id,
        payload={"score": 0.5},
        mastery_snapshot={"level": "operator", "progress_to_next": 0.3},
        actor=CaseEventActor(id=actor_id, email="ops@neft.io"),
        request_id="req-2",
        trace_id="trace-2",
    )
    db_session.commit()

    record = (
        db_session.query(DecisionMemoryRecord)
        .filter(DecisionMemoryRecord.case_id == case.id, DecisionMemoryRecord.decision_ref_id == export.id)
        .one()
    )
    assert record.decision_type == "action"
    assert record.decision_at is not None
    assert record.score_snapshot == {"score": 0.5}
    assert record.mastery_snapshot == {"level": "operator", "progress_to_next": 0.3}


def test_verify_export_detects_tamper(
    client: TestClient,
    db_session: Session,
    make_jwt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.case_export_service.ExportStorage", FakeExportStorage)
    monkeypatch.setattr("app.routers.admin.exports.ExportStorage", FakeExportStorage)
    monkeypatch.setattr("app.services.case_export_verification_service.ExportStorage", FakeExportStorage)
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1, "email": "admin@neft.io"})
    actor_id = str(uuid4())

    case = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.OPERATION,
        title="case",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
    )
    db_session.add(case)
    db_session.commit()

    export = create_export(
        db_session,
        kind="CASE",
        case_id=case.id,
        payload={"case": {"id": case.id, "status": "TRIAGE"}},
        mastery_snapshot=None,
        actor=CaseEventActor(id=actor_id, email="ops@neft.io"),
        request_id="req-3",
        trace_id="trace-3",
    )
    db_session.commit()

    resp = client.post(
        f"/api/core/v1/admin/exports/{export.id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["content_hash_verified"] is True
    assert body["artifact_signature_verified"] is True
    assert body["audit_chain_verified"] is True

    FakeExportStorage.objects[export.object_key] = (b"{\"tampered\":true}", "application/json")

    resp = client.post(
        f"/api/core/v1/admin/exports/{export.id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["content_hash_verified"] is False
