from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.dependencies.client import client_portal_user
from app.domains.documents.models import Document
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
    db.query(Document).delete()
    db.commit()


def test_create_outbound_draft_201(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    app.dependency_overrides[_service] = lambda: _override_service(test_db_session, storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            response = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Акт сверки за январь", "doc_type": "ACT", "description": "Просьба подписать"},
            )
        assert response.status_code == 201
        payload = response.json()
        assert payload["direction"] == "OUTBOUND"
        assert payload["status"] == "DRAFT"
        assert payload["files"] == []
    finally:
        app.dependency_overrides.clear()


def test_upload_file_and_list_files(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
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


def test_download_file_ok(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    app.dependency_overrides[_service] = lambda: _override_service(test_db_session, storage)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    file_bytes = b"pdf-bytes"

    try:
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": "Исходящий документ", "doc_type": "ACT"},
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


def test_acl_other_client_cannot_download(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    token_a = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    token_b = make_jwt(roles=("CLIENT_USER",), client_id="client-b")

    try:
        app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
        app.dependency_overrides[_service] = lambda: _override_service(test_db_session, storage)
        with TestClient(app) as api_client:
            create = api_client.post(
                "/api/core/client/documents",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"title": "Исходящий документ", "doc_type": "ACT"},
            )
            document_id = create.json()["id"]
            upload = api_client.post(
                f"/api/core/client/documents/{document_id}/upload",
                headers={"Authorization": f"Bearer {token_a}"},
                files={"file": ("act.pdf", b"abc", "application/pdf")},
            )
            file_id = upload.json()["id"]

        app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-b"}
        app.dependency_overrides[_service] = lambda: _override_service(test_db_session, storage)
        with TestClient(app) as api_client:
            denied = api_client.get(
                f"/api/core/client/documents/files/{file_id}/download",
                headers={"Authorization": f"Bearer {token_b}"},
            )

        assert denied.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_upload_forbidden_when_not_draft(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
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

            document = test_db_session.query(Document).filter(Document.id == document_id).one()
            document.status = "SENT"
            test_db_session.add(document)
            test_db_session.commit()

            upload = api_client.post(
                f"/api/core/client/documents/{document_id}/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("act.pdf", b"abc", "application/pdf")},
            )
        assert upload.status_code in {400, 409}
    finally:
        app.dependency_overrides.clear()
