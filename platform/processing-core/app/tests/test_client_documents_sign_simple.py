from __future__ import annotations

from datetime import date

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.client import client_portal_user
from app.db import Base, get_db
from app.main import app
from app.domains.documents.models import Document, DocumentDirection, DocumentFile, DocumentSignature, DocumentStatus, DocumentTimelineEvent
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.service import DocumentsService
from app.routers.client_documents_v1 import _service


class _StorageStub:
    def __init__(self, data: dict[str, bytes]):
        self.data = data

    def get_object_stream(self, key: str):
        import io

        if key not in self.data:
            raise FileNotFoundError(key)
        return io.BytesIO(self.data[key])


class _StorageMissing:
    def get_object_stream(self, key: str):
        raise FileNotFoundError(key)


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


@pytest.fixture(autouse=True)
def _allow_prod_mock_guardrails(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")


@pytest.fixture()
def db_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    if "users" not in Base.metadata.tables:
        Table("users", Base.metadata, Column("id", String(64), primary_key=True), extend_existing=True)
    if "certificates" not in Base.metadata.tables:
        Table("certificates", Base.metadata, Column("id", String(64), primary_key=True), extend_existing=True)

    for table in _clone_tables_without_duplicate_indexes(
        Base.metadata.tables["users"],
        Base.metadata.tables["certificates"],
        Document.__table__,
        DocumentFile.__table__,
        DocumentSignature.__table__,
        DocumentTimelineEvent.__table__,
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


def _cleanup(db_session_factory: sessionmaker[Session]) -> None:
    with db_session_factory() as db:
        db.execute(text("INSERT OR IGNORE INTO users (id) VALUES ('20000000-0000-0000-0000-000000000001')"))
        db.query(DocumentTimelineEvent).delete()
        db.query(DocumentSignature).delete()
        db.query(DocumentFile).delete()
        db.query(Document).delete()
        db.commit()


def _mk_doc(
    db_session_factory: sessionmaker[Session],
    *,
    client_id: str = "client-a",
    direction: str = DocumentDirection.INBOUND.value,
    status: str = DocumentStatus.READY_TO_SIGN.value,
) -> str:
    with db_session_factory() as db:
        item = Document(
            id="10000000-0000-0000-0000-000000000001",
            tenant_id=0,
            client_id=client_id,
            document_type="ACT",
            period_from=date(2025, 1, 1),
            period_to=date(2025, 1, 1),
            version=1,
            direction=direction,
            title="doc",
            status=status,
        )
        db.add(item)
        db.commit()
    return "10000000-0000-0000-0000-000000000001"


def _attach_file(db_session_factory: sessionmaker[Session], document_id: str, storage_key: str = "s3://doc.pdf") -> None:
    with db_session_factory() as db:
        db.add(
            DocumentFile(
                id="10000000-0000-0000-0000-000000000002",
                document_id=document_id,
                file_type="PDF",
                bucket="client-documents",
                object_key=storage_key,
                storage_key=storage_key,
                filename="doc.pdf",
                mime="application/pdf",
                size=4,
                size_bytes=4,
                content_type="application/pdf",
                sha256="",
            )
        )
        db.commit()


def _install_overrides(storage, *, client_id: str = "client-a", user_id: str = "20000000-0000-0000-0000-000000000001") -> None:
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": client_id, "user_id": user_id}

    def override_service(db: Session = Depends(get_db)) -> DocumentsService:
        return DocumentsService(repo=DocumentsRepository(db=db), storage=storage)

    app.dependency_overrides[_service] = override_service


def _sign(c: TestClient, doc_id: str, token: str):
    return c.post(
        f"/api/core/client/documents/{doc_id}/sign",
        json={"consent_text_version": "v1", "checkbox_confirmed": True, "signer_full_name": "Ivan Petrov"},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_sign_forbidden_for_other_client(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    doc_id = _mk_doc(db_session_factory, client_id="client-b")
    _attach_file(db_session_factory, doc_id)
    _install_overrides(_StorageStub({"s3://doc.pdf": b"pdf"}), client_id="client-a")
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            resp = _sign(c, doc_id, token)
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_sign_forbidden_for_outbound(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    doc_id = _mk_doc(db_session_factory, direction=DocumentDirection.OUTBOUND.value)
    _attach_file(db_session_factory, doc_id)
    _install_overrides(_StorageStub({"s3://doc.pdf": b"pdf"}))
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            resp = _sign(c, doc_id, token)
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["type"] == "http_error"
        assert body["error"]["message"] == "SIGN_NOT_ALLOWED_FOR_OUTBOUND"
    finally:
        app.dependency_overrides.clear()

def test_sign_requires_ready_status(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    doc_id = _mk_doc(db_session_factory, status=DocumentStatus.DRAFT.value)
    _attach_file(db_session_factory, doc_id)
    _install_overrides(_StorageStub({"s3://doc.pdf": b"pdf"}))
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            resp = _sign(c, doc_id, token)
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["type"] == "http_error"
        assert body["error"]["message"] == "DOC_NOT_READY_TO_SIGN"
    finally:
        app.dependency_overrides.clear()

def test_sign_creates_signature_and_updates_doc(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    doc_id = _mk_doc(db_session_factory)
    _attach_file(db_session_factory, doc_id)
    _install_overrides(_StorageStub({"s3://doc.pdf": b"pdf"}))
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            resp = _sign(c, doc_id, token)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == DocumentStatus.SIGNED_CLIENT.value

        with db_session_factory() as db:
            sig_count = db.query(DocumentSignature).filter(DocumentSignature.document_id == doc_id).count()
            assert sig_count == 1
            doc = db.query(Document).filter(Document.id == doc_id).one()
            assert doc.status == DocumentStatus.SIGNED_CLIENT.value
            event = (
                db.query(DocumentTimelineEvent)
                .filter(DocumentTimelineEvent.document_id == doc_id)
                .filter(DocumentTimelineEvent.event_type == "SIGNED_CLIENT")
                .one_or_none()
            )
            assert event is not None
    finally:
        app.dependency_overrides.clear()


def test_signed_inbound_detail_exposes_signature_hash_and_file_kind(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    doc_id = _mk_doc(db_session_factory)
    _attach_file(db_session_factory, doc_id)
    _install_overrides(_StorageStub({"s3://doc.pdf": b"pdf"}))
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            signed = _sign(c, doc_id, token)
            detail = c.get(
                f"/api/core/client/documents/{doc_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert signed.status_code == 200
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["document_hash_sha256"] == signed.json()["document_hash_sha256"]
        assert payload["requires_action"] is False
        assert payload["action_code"] is None
        assert payload["files"][0]["kind"] == "PDF"
    finally:
        app.dependency_overrides.clear()


def test_sign_idempotent(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    doc_id = _mk_doc(db_session_factory)
    _attach_file(db_session_factory, doc_id)
    _install_overrides(_StorageStub({"s3://doc.pdf": b"pdf"}))
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            first = _sign(c, doc_id, token)
            second = _sign(c, doc_id, token)
        assert first.status_code == 200
        assert second.status_code == 200
        with db_session_factory() as db:
            sig_count = db.query(DocumentSignature).filter(DocumentSignature.document_id == doc_id).count()
            assert sig_count == 1
    finally:
        app.dependency_overrides.clear()


def test_sign_fails_if_file_missing(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    doc_id = _mk_doc(db_session_factory)
    _attach_file(db_session_factory, doc_id, storage_key="s3://missing.pdf")
    _install_overrides(_StorageMissing())
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            resp = _sign(c, doc_id, token)
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["type"] == "http_error"
        assert body["error"]["message"] == "DOC_FILE_MISSING"
    finally:
        app.dependency_overrides.clear()
