from __future__ import annotations

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as app_main
from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.domains.documents.models import Document, DocumentFile, DocumentTimelineEvent
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.service import DocumentsService
from app.main import app
from app.routers.client_documents_v1 import _service


class _InMemoryStorage:
    def __init__(self):
        self.items: dict[str, bytes] = {}

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


def _install_overrides(storage: _InMemoryStorage, *, client_id: str) -> None:
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": client_id, "sub": f"user-{client_id}"}

    def override_service(db: Session = Depends(get_db)) -> DocumentsService:
        return DocumentsService(repo=DocumentsRepository(db=db), storage=storage)

    app.dependency_overrides[_service] = override_service


def _cleanup(db_session_factory: sessionmaker[Session]) -> None:
    with db_session_factory() as db:
        db.query(DocumentTimelineEvent).delete()
        db.query(DocumentFile).delete()
        db.query(Document).delete()
        db.commit()


def test_timeline_has_document_created_after_create(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage, client_id="client-a")
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Outbound document", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]
            timeline = api_client.get(
                f"/api/core/client/documents/{document_id}/timeline",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert timeline.status_code == 200
        events = timeline.json()
        assert len(events) == 1
        assert events[0]["event_type"] == "DOCUMENT_CREATED"
    finally:
        app.dependency_overrides.clear()


def test_timeline_adds_file_uploaded(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage, client_id="client-a")
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
            timeline = api_client.get(
                f"/api/core/client/documents/{document_id}/timeline",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert timeline.status_code == 200
        events = timeline.json()
        uploaded = next(item for item in events if item["event_type"] == "FILE_UPLOADED")
        assert uploaded["meta"]["filename"] == "act.pdf"
    finally:
        app.dependency_overrides.clear()


def test_submit_changes_status_and_writes_timeline(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage, client_id="client-a")
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Outbound document", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]
            api_client.post(
                f"/api/core/client/documents/{document_id}/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("act.pdf", b"hello-pdf", "application/pdf")},
            )

            submit = api_client.post(
                f"/api/core/client/documents/{document_id}/submit",
                headers={"Authorization": f"Bearer {token}"},
            )
            details = api_client.get(
                f"/api/core/client/documents/{document_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            timeline = api_client.get(
                f"/api/core/client/documents/{document_id}/timeline",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert submit.status_code == 200
        assert details.json()["status"] == "READY_TO_SEND"
        status_event = next(item for item in timeline.json() if item["event_type"] == "STATUS_CHANGED")
        assert status_event["meta"] == {"from": "DRAFT", "to": "READY_TO_SEND"}
    finally:
        app.dependency_overrides.clear()


def test_submit_without_files_returns_409(make_jwt, db_session_factory):
    _cleanup(db_session_factory)
    storage = _InMemoryStorage()
    _install_overrides(storage, client_id="client-a")
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Outbound document", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]
            submit = api_client.post(
                f"/api/core/client/documents/{document_id}/submit",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert submit.status_code == 409
        assert submit.json()["error"]["type"] == "http_error"
        assert submit.json()["error"]["message"] == "missing_files"
    finally:
        app.dependency_overrides.clear()


def test_acl_timeline_other_client_404(make_jwt, db_session_factory):
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

        _install_overrides(storage, client_id="client-b")
        with TestClient(app) as api_client:
            timeline = api_client.get(
                f"/api/core/client/documents/{document_id}/timeline",
                headers={"Authorization": f"Bearer {token_b}"},
            )

        assert timeline.status_code == 404
    finally:
        app.dependency_overrides.clear()
