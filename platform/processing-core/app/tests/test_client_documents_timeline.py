from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.dependencies.client import client_portal_user
from app.domains.documents.models import Document, DocumentTimelineEvent
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


def _override_service(db, storage: _InMemoryStorage):
    return DocumentsService(repo=DocumentsRepository(db=db), storage=storage)


def _cleanup(db) -> None:
    db.query(DocumentTimelineEvent).delete()
    db.query(Document).delete()
    db.commit()


def test_timeline_has_document_created_after_create(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a", "sub": "user-a"}
    app.dependency_overrides[_service] = lambda: _override_service(test_db_session, storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Исходящий документ", "doc_type": "ACT"},
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


def test_timeline_adds_file_uploaded(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a", "sub": "user-a"}
    app.dependency_overrides[_service] = lambda: _override_service(test_db_session, storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Исходящий документ", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]
            api_client.post(
                f"/api/core/client/documents/{document_id}/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("act.pdf", b"hello-pdf", "application/pdf")},
            )
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


def test_submit_changes_status_and_writes_timeline(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a", "sub": "user-a"}
    app.dependency_overrides[_service] = lambda: _override_service(test_db_session, storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Исходящий документ", "doc_type": "ACT"},
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


def test_submit_without_files_returns_409(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a", "sub": "user-a"}
    app.dependency_overrides[_service] = lambda: _override_service(test_db_session, storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Исходящий документ", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]
            submit = api_client.post(
                f"/api/core/client/documents/{document_id}/submit",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert submit.status_code == 409
        assert submit.json()["detail"] == "missing_files"
    finally:
        app.dependency_overrides.clear()


def test_acl_timeline_other_client_404(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    token_a = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    token_b = make_jwt(roles=("CLIENT_USER",), client_id="client-b")

    try:
        app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a", "sub": "user-a"}
        app.dependency_overrides[_service] = lambda: _override_service(test_db_session, storage)
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"title": "Исходящий документ", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]

        app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-b", "sub": "user-b"}
        app.dependency_overrides[_service] = lambda: _override_service(test_db_session, storage)
        with TestClient(app) as api_client:
            timeline = api_client.get(
                f"/api/core/client/documents/{document_id}/timeline",
                headers={"Authorization": f"Bearer {token_b}"},
            )

        assert timeline.status_code == 404
    finally:
        app.dependency_overrides.clear()
