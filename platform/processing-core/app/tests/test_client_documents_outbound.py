from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as app_main
from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.main import app
from app.domains.documents.models import Document, DocumentEdoState, DocumentFile, DocumentTimelineEvent
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.service import DocumentsService
from app.models.audit_log import AuditLog
from app.models.client_actions import DocumentAcknowledgement
from app.models.decision_result import DecisionResult
from app.models.risk_decision import RiskDecision
from app.models.risk_score import RiskLevel
from app.models.risk_types import RiskDecisionActor, RiskDecisionType, RiskSubjectType
from app.routers.client_documents_v1 import _service


class _InMemoryStorage:
    def __init__(self):
        self.items: dict[str, bytes] = {}
        self.bucket = "client-documents"

    def ensure_bucket(self) -> None:
        return

    def put_object(self, key: str, payload: bytes, content_type: str) -> None:
        self.items[key] = payload

    def get_object_stream(self, key: str):
        from io import BytesIO

        return BytesIO(self.items[key])


def _clone_tables_without_duplicate_indexes(*tables):
    metadata = MetaData()
    cloned_tables = []
    for table in tables:
        cloned = table.to_metadata(metadata)
        seen = set()
        for index in list(cloned.indexes):
            if index.name in seen:
                cloned.indexes.remove(index)
            else:
                seen.add(index.name)
        cloned_tables.append(cloned)
    return cloned_tables


@pytest.fixture()
def db_session_factory(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    monkeypatch.setattr(app_main.settings, "APP_ENV", "dev", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    for table in _clone_tables_without_duplicate_indexes(
        Document.__table__,
        DocumentFile.__table__,
        DocumentEdoState.__table__,
        DocumentTimelineEvent.__table__,
        DocumentAcknowledgement.__table__,
        AuditLog.__table__,
        RiskDecision.__table__,
        DecisionResult.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

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
    try:
        yield testing_session_local
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _install_overrides(
    storage: _InMemoryStorage,
    *,
    client_id: str = "client-a",
    token_payload: dict | None = None,
) -> None:
    app_main.settings.APP_ENV = "dev"
    payload = token_payload or {"client_id": client_id}
    app.dependency_overrides[client_portal_user] = lambda: payload

    def override_service(db: Session = Depends(get_db)) -> DocumentsService:
        return DocumentsService(repo=DocumentsRepository(db=db), storage=storage)

    app.dependency_overrides[_service] = override_service


def _cleanup(db_session_factory: sessionmaker[Session]) -> None:
    with db_session_factory() as db:
        db.query(DecisionResult).delete()
        db.query(RiskDecision).delete()
        db.query(DocumentAcknowledgement).delete()
        db.query(AuditLog).delete()
        db.query(DocumentEdoState).delete()
        db.query(DocumentTimelineEvent).delete()
        db.query(DocumentFile).delete()
        db.query(Document).delete()
        db.commit()


def test_create_outbound_draft_201(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            response = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Act reconciliation", "doc_type": "ACT", "description": "Please sign"},
            )
        assert response.status_code == 201
        payload = response.json()
        assert payload["direction"] == "OUTBOUND"
        assert payload["status"] == "DRAFT"
        assert payload["files"] == []
    finally:
        app.dependency_overrides.clear()


def test_canonical_read_parity_fields_for_outbound(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    file_bytes = b"hello-pdf"
    expected_hash = hashlib.sha256(file_bytes).hexdigest()

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Reconciliation act", "doc_type": "ACT"},
            )
            assert create.status_code == 201
            created_payload = create.json()
            assert created_payload["requires_action"] is True
            assert created_payload["action_code"] == "UPLOAD_OR_SUBMIT"
            document_id = created_payload["id"]

            list_before = api_client.get(
                "/api/core/client/documents?direction=outbound",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert list_before.status_code == 200
            item_before = list_before.json()["items"][0]
            assert item_before["requires_action"] is True
            assert item_before["action_code"] == "UPLOAD_OR_SUBMIT"

            upload = api_client.post(
                f"/api/core/client/documents/{document_id}/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("act.pdf", file_bytes, "application/pdf")},
            )
            assert upload.status_code == 201
            upload_payload = upload.json()
            assert upload_payload["kind"] == "PDF"
            assert upload_payload["sha256"] == expected_hash

            details = api_client.get(
                f"/api/core/client/documents/{document_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert details.status_code == 200
            detail_payload = details.json()
            assert detail_payload["document_hash_sha256"] == expected_hash
            assert detail_payload["files"][0]["kind"] == "PDF"
            assert detail_payload["requires_action"] is True
            assert detail_payload["action_code"] == "UPLOAD_OR_SUBMIT"

            submit = api_client.post(
                f"/api/core/client/documents/{document_id}/submit",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert submit.status_code == 200
            submitted_payload = submit.json()
            assert submitted_payload["requires_action"] is True
            assert submitted_payload["action_code"] == "SEND_TO_EDO"
            assert submitted_payload["document_hash_sha256"] == expected_hash

            list_after = api_client.get(
                "/api/core/client/documents?direction=outbound",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert list_after.status_code == 200
            item_after = list_after.json()["items"][0]
            assert item_after["requires_action"] is True
            assert item_after["action_code"] == "SEND_TO_EDO"
    finally:
        app.dependency_overrides.clear()


def test_canonical_list_reads_shared_ack_edo_and_period_fields(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    ack_at = datetime(2025, 2, 5, 6, 7, 8, tzinfo=timezone.utc)
    today = datetime.now(timezone.utc).date().isoformat()

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Outbound inbox parity", "doc_type": "ACT"},
            )
            assert create.status_code == 201
            document_id = create.json()["id"]

        with db_session_factory() as db:
            db.execute(
                text("UPDATE documents SET ack_at = :ack_at WHERE id = :document_id"),
                {"ack_at": ack_at, "document_id": document_id},
            )
            db.add(
                DocumentEdoState(
                    id="10000000-0000-0000-0000-0000000000ee",
                    document_id=document_id,
                    client_id="client-a",
                    provider="mock",
                    provider_mode="mock",
                    edo_status="REJECTED",
                    attempts_send=1,
                    attempts_poll=0,
                )
            )
            db.commit()

        with TestClient(app) as api_client:
            listing = api_client.get(
                "/api/core/client/documents?direction=outbound",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert listing.status_code == 200
        payload = listing.json()
        item = payload["items"][0]
        assert item["ack_at"].startswith("2025-02-05T06:07:08")
        assert item["edo_status"] == "REJECTED"
        assert item["period_from"] == today
        assert item["period_to"] == today
        assert item["requires_action"] is True
        assert item["action_code"] == "UPLOAD_OR_SUBMIT"
    finally:
        app.dependency_overrides.clear()


def test_canonical_detail_reads_shared_ack_and_risk_fields(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    ack_at = datetime(2025, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
    decided_at = datetime(2025, 2, 4, 10, 11, 12, tzinfo=timezone.utc)
    decision_id = "decision-doc-1"
    explain = {"policy": "doc_review", "factors": ["missing_stamp"], "thresholds": {"score": 60}}

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Acknowledgement candidate", "doc_type": "ACT"},
            )
            assert create.status_code == 201
            document_id = create.json()["id"]

        with db_session_factory() as db:
            db.execute(
                text("UPDATE documents SET ack_at = :ack_at, document_hash = :document_hash WHERE id = :document_id"),
                {"ack_at": ack_at, "document_hash": "legacy-ack-hash", "document_id": document_id},
            )
            db.add(
                DocumentAcknowledgement(
                    id="10000000-0000-0000-0000-0000000000aa",
                    tenant_id=0,
                    client_id="client-a",
                    document_type="ACT",
                    document_id=document_id,
                    document_hash="legacy-ack-hash",
                    ack_by_user_id="user-1",
                    ack_by_email="client@example.com",
                    ack_ip="127.0.0.1",
                    ack_user_agent="pytest",
                    ack_at=ack_at,
                    ack_method="PORTAL_ACK",
                )
            )
            db.add(
                RiskDecision(
                    id="10000000-0000-0000-0000-0000000000bb",
                    decision_id=decision_id,
                    subject_type=RiskSubjectType.DOCUMENT,
                    subject_id=document_id,
                    score=61,
                    risk_level=RiskLevel.MEDIUM,
                    threshold_set_id="threshold-set-1",
                    policy_id="policy-doc-1",
                    outcome=RiskDecisionType.ALLOW_WITH_REVIEW,
                    reasons=["missing_stamp"],
                    features_snapshot={"missing_stamp": True},
                    decided_at=decided_at,
                    decided_by=RiskDecisionActor.SYSTEM,
                    audit_id="10000000-0000-0000-0000-0000000000cc",
                )
            )
            db.add(
                DecisionResult(
                    id="10000000-0000-0000-0000-0000000000dd",
                    decision_id=decision_id,
                    decision_version="v1",
                    action="DOCUMENT_FINALIZE",
                    outcome="ALLOW_WITH_REVIEW",
                    risk_score=61,
                    rule_hits=["missing_stamp"],
                    model_version="model-v1",
                    context_hash="ctx-hash-1",
                    explain=explain,
                )
            )
            db.commit()

        with TestClient(app) as api_client:
            detail = api_client.get(
                f"/api/core/client/documents/{document_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert detail.status_code == 200
        payload = detail.json()
        assert payload["ack_at"].startswith("2025-02-03T04:05:06")
        assert payload["ack_details"] == {
            "ack_by_user_id": "user-1",
            "ack_by_email": "client@example.com",
            "ack_ip": "127.0.0.1",
            "ack_user_agent": "pytest",
            "ack_method": "PORTAL_ACK",
            "ack_at": payload["ack_at"],
        }
        assert payload["risk"] == {
            "state": "REQUIRE_OVERRIDE",
            "decided_at": payload["risk"]["decided_at"],
            "decision_id": decision_id,
        }
        assert payload["risk"]["decided_at"].startswith("2025-02-04T10:11:12")
        assert payload["risk_explain"] == explain
    finally:
        app.dependency_overrides.clear()


def test_upload_file_and_list_files(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Outbound document", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]

            upload = api_client.post(
                f"/api/core/client/documents/{document_id}/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("act.pdf", b"hello-pdf", "application/pdf")},
            )
            assert upload.status_code == 201

            details = api_client.get(
                f"/api/core/client/documents/{document_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert details.status_code == 200
        assert len(details.json()["files"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_download_file_ok(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    file_bytes = b"pdf-bytes"

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Outbound document", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]

            upload = api_client.post(
                f"/api/core/client/documents/{document_id}/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("act.pdf", file_bytes, "application/pdf")},
            )
            file_id = upload.json()["id"]

            download = api_client.get(
                f"/api/core/client/documents/files/{file_id}/download",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert download.status_code == 200
        assert download.content == file_bytes
        assert "attachment;" in (download.headers.get("content-disposition") or "")
    finally:
        app.dependency_overrides.clear()


def test_acl_other_client_cannot_download(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    token_a = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    token_b = make_jwt(roles=("CLIENT_USER",), client_id="client-b")

    try:
        _install_overrides(storage, client_id="client-a")
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"title": "Outbound document", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]
            upload = api_client.post(
                f"/api/core/client/documents/{document_id}/upload",
                headers={"Authorization": f"Bearer {token_a}"},
                files={"file": ("act.pdf", b"abc", "application/pdf")},
            )
            file_id = upload.json()["id"]

        _install_overrides(storage, client_id="client-b")
        with TestClient(app) as api_client:
            denied = api_client.get(
                f"/api/core/client/documents/files/{file_id}/download",
                headers={"Authorization": f"Bearer {token_b}"},
            )

        assert denied.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_upload_forbidden_when_not_draft(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Outbound document", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]

            with db_session_factory() as db:
                document = db.query(Document).filter(Document.id == document_id).one()
                document.status = "SENT"
                db.add(document)
                db.commit()

            upload = api_client.post(
                f"/api/core/client/documents/{document_id}/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("act.pdf", b"abc", "application/pdf")},
            )
        assert upload.status_code in {400, 409}
    finally:
        app.dependency_overrides.clear()
