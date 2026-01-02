from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models.audit_retention import AuditLegalHold, AuditLegalHoldScope, AuditPurgeLog
from app.models.case_exports import CaseExport, CaseExportKind
from app.models.cases import Case, CaseEvent, CaseKind, CasePriority, CaseQueue, CaseStatus
from app.services.audit_purge_service import purge_expired_exports
from app.services.case_events_service import CaseEventActor
from app.services.case_export_service import create_export


class FakeExportStorage:
    objects: dict[str, tuple[bytes, str]] = {}
    deleted: list[str] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    def put_bytes(self, key: str, content: bytes, *, content_type: str) -> None:
        self.objects[key] = (content, content_type)

    def delete(self, key: str) -> None:
        self.deleted.append(key)
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


@pytest.fixture(autouse=True)
def _reset_fake_storage() -> None:
    FakeExportStorage.objects = {}
    FakeExportStorage.deleted = []


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Case.__table__.create(bind=engine)
    CaseEvent.__table__.create(bind=engine)
    CaseExport.__table__.create(bind=engine)
    AuditLegalHold.__table__.create(bind=engine)
    AuditPurgeLog.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        AuditPurgeLog.__table__.drop(bind=engine)
        AuditLegalHold.__table__.drop(bind=engine)
        CaseExport.__table__.drop(bind=engine)
        CaseEvent.__table__.drop(bind=engine)
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


def _create_case(db_session: Session) -> Case:
    case = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.OPERATION,
        title="case",
        status=CaseStatus.TRIAGE,
        queue=CaseQueue.GENERAL,
        priority=CasePriority.MEDIUM,
        escalation_level=0,
    )
    db_session.add(case)
    db_session.commit()
    return case


def test_create_export_redacts_payload_and_hashes_stably(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.case_export_service.ExportStorage", FakeExportStorage)
    case = _create_case(db_session)
    payload = {
        "user": {"email": "ops@neft.io", "token": "secret-token"},
        "notes": "call me +7 999 123 45 12",
    }

    first = create_export(
        db_session,
        kind="EXPLAIN",
        case_id=case.id,
        payload=payload,
        mastery_snapshot=None,
        actor=CaseEventActor(id=str(uuid4()), email="admin@neft.io"),
        request_id="req-1",
        trace_id="trace-1",
    )
    second = create_export(
        db_session,
        kind="EXPLAIN",
        case_id=case.id,
        payload=payload,
        mastery_snapshot=None,
        actor=CaseEventActor(id=str(uuid4()), email="admin@neft.io"),
        request_id="req-2",
        trace_id="trace-2",
    )

    assert first.content_sha256 == second.content_sha256
    stored_payload = json.loads(FakeExportStorage.objects[first.object_key][0].decode("utf-8"))
    assert stored_payload["user"]["email"]["redacted"] is True
    assert stored_payload["user"]["token"]["redacted"] is True


def test_create_export_emits_case_event(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.case_export_service.ExportStorage", FakeExportStorage)
    case = _create_case(db_session)
    export = create_export(
        db_session,
        kind="DIFF",
        case_id=case.id,
        payload={"diff": {"score": 1}},
        mastery_snapshot=None,
        actor=CaseEventActor(id=str(uuid4()), email="ops@neft.io"),
        request_id="req-10",
        trace_id="trace-10",
    )
    db_session.commit()

    event = db_session.query(CaseEvent).filter(CaseEvent.case_id == case.id).one()
    assert event.type.value == "EXPORT_CREATED"
    assert event.payload_redacted["artifact"]["id"] == export.id
    assert event.payload_redacted["content_sha256"] == export.content_sha256


def test_download_endpoint_returns_signed_url(
    client: TestClient,
    db_session: Session,
    make_jwt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.case_export_service.ExportStorage", FakeExportStorage)
    monkeypatch.setattr("app.routers.admin.exports.ExportStorage", FakeExportStorage)
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1, "email": "admin@neft.io"})
    case = _create_case(db_session)
    export = create_export(
        db_session,
        kind="CASE",
        case_id=case.id,
        payload={"case": {"id": case.id}},
        mastery_snapshot=None,
        actor=CaseEventActor(id=str(uuid4()), email="admin@neft.io"),
        request_id="req-20",
        trace_id="trace-20",
    )
    db_session.commit()

    resp = client.post(
        f"/api/core/v1/admin/exports/{export.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert export.content_sha256 == body["content_sha256"]
    assert body["url"].startswith("https://exports.local/")


def test_purge_exports_respects_legal_hold(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.audit_purge_service.ExportStorage", FakeExportStorage)
    now = datetime.now(timezone.utc)
    case = _create_case(db_session)
    export = CaseExport(
        id=str(uuid4()),
        case_id=case.id,
        kind=CaseExportKind.EXPLAIN,
        object_key="exports/case-1/explain/2025/01/export.json",
        content_type="application/json",
        content_sha256="abc",
        size_bytes=10,
        created_at=now - timedelta(days=200),
        retention_until=now - timedelta(days=1),
    )
    hold = AuditLegalHold(
        scope=AuditLegalHoldScope.CASE.value,
        case_id=case.id,
        reason="legal hold",
        active=True,
    )
    db_session.add_all([export, hold])
    db_session.commit()

    result = purge_expired_exports(
        db_session,
        now=now,
        retention_days=30,
        dry_run=False,
        purged_by="test-suite",
    )

    assert result.purged == 0
    assert result.skipped_hold == 1
    assert db_session.query(CaseExport).count() == 1
