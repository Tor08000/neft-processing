from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.client import client_portal_user
from app.domains.documents.models import Document, DocumentTimelineEvent
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.service import DocumentsService
from app.main import app
from app.routers.admin_documents_v1 import _service as admin_service_dep
from app.routers.client_documents_v1 import _service as client_service_dep


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


def test_admin_create_inbound_document_success(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[require_admin_user] = lambda: {"roles": ["ADMIN"], "sub": "admin-1"}
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a", "sub": "user-a"}
    app.dependency_overrides[admin_service_dep] = lambda: _override_service(test_db_session, storage)
    app.dependency_overrides[client_service_dep] = lambda: _override_service(test_db_session, storage)
    admin_token = make_jwt(roles=("ADMIN",), aud="neft-admin")
    client_token = make_jwt(roles=("CLIENT_USER",), client_id="client-a", aud="neft-client")

    try:
        with TestClient(app) as api_client:
            created = api_client.post(
                "/api/core/admin/clients/client-a/documents",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"title": "Акт за январь", "category": "ACT", "description": "Акт", "attach_mode": "UPLOAD"},
            )
            assert created.status_code == 201
            payload = created.json()
            assert payload["direction"] == "INBOUND"
            assert payload["sender_type"] == "NEFT"

            listed = api_client.get(
                "/api/core/client/documents?direction=INBOUND",
                headers={"Authorization": f"Bearer {client_token}"},
            )
            assert listed.status_code == 200
            ids = [item["id"] for item in listed.json()["items"]]
            assert payload["id"] in ids
    finally:
        app.dependency_overrides.clear()


def test_admin_attach_file_inbound_success(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[require_admin_user] = lambda: {"roles": ["ADMIN"], "sub": "admin-1"}
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a", "sub": "user-a"}
    app.dependency_overrides[admin_service_dep] = lambda: _override_service(test_db_session, storage)
    app.dependency_overrides[client_service_dep] = lambda: _override_service(test_db_session, storage)
    admin_token = make_jwt(roles=("ADMIN",), aud="neft-admin")
    client_token = make_jwt(roles=("CLIENT_USER",), client_id="client-a", aud="neft-client")

    try:
        with TestClient(app) as api_client:
            created = api_client.post(
                "/api/core/admin/clients/client-a/documents",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"title": "Акт за январь", "category": "ACT", "attach_mode": "UPLOAD"},
            )
            document_id = created.json()["id"]

            uploaded = api_client.post(
                f"/api/core/admin/documents/{document_id}/files",
                headers={"Authorization": f"Bearer {admin_token}"},
                files={"file": ("act.pdf", b"pdf-binary", "application/pdf")},
            )
            assert uploaded.status_code == 200
            file_id = uploaded.json()["id"]

            files = api_client.get(
                f"/api/core/client/documents/{document_id}/files",
                headers={"Authorization": f"Bearer {client_token}"},
            )
            assert files.status_code == 200
            assert len(files.json()) == 1

            downloaded = api_client.get(
                f"/api/core/client/documents/files/{file_id}/download",
                headers={"Authorization": f"Bearer {client_token}"},
            )
            assert downloaded.status_code == 200
            assert downloaded.content == b"pdf-binary"
    finally:
        app.dependency_overrides.clear()


def test_client_cannot_access_other_clients_inbound(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[require_admin_user] = lambda: {"roles": ["ADMIN"], "sub": "admin-1"}
    app.dependency_overrides[admin_service_dep] = lambda: _override_service(test_db_session, storage)
    app.dependency_overrides[client_service_dep] = lambda: _override_service(test_db_session, storage)
    admin_token = make_jwt(roles=("ADMIN",), aud="neft-admin")

    try:
        with TestClient(app) as api_client:
            created = api_client.post(
                "/api/core/admin/clients/client-b/documents",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"title": "Входящий", "attach_mode": "UPLOAD"},
            )
            document_id = created.json()["id"]

            app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a", "sub": "user-a"}
            client_a_token = make_jwt(roles=("CLIENT_USER",), client_id="client-a", aud="neft-client")
            denied = api_client.get(
                f"/api/core/client/documents/{document_id}",
                headers={"Authorization": f"Bearer {client_a_token}"},
            )
            assert denied.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_timeline_created_and_file_uploaded(make_jwt, test_db_session):
    _cleanup(test_db_session)
    storage = _InMemoryStorage()
    app.dependency_overrides[require_admin_user] = lambda: {"roles": ["ADMIN"], "sub": "admin-1"}
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a", "sub": "user-a"}
    app.dependency_overrides[admin_service_dep] = lambda: _override_service(test_db_session, storage)
    app.dependency_overrides[client_service_dep] = lambda: _override_service(test_db_session, storage)
    admin_token = make_jwt(roles=("ADMIN",), aud="neft-admin")
    client_token = make_jwt(roles=("CLIENT_USER",), client_id="client-a", aud="neft-client")

    try:
        with TestClient(app) as api_client:
            created = api_client.post(
                "/api/core/admin/clients/client-a/documents",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"title": "Акт за январь", "attach_mode": "UPLOAD"},
            )
            document_id = created.json()["id"]

            timeline_after_create = api_client.get(
                f"/api/core/client/documents/{document_id}/timeline",
                headers={"Authorization": f"Bearer {client_token}"},
            )
            assert timeline_after_create.status_code == 200
            created_events = [item for item in timeline_after_create.json() if item["event_type"] == "DOCUMENT_CREATED"]
            assert created_events

            api_client.post(
                f"/api/core/admin/documents/{document_id}/files",
                headers={"Authorization": f"Bearer {admin_token}"},
                files={"file": ("акт.pdf", b"timeline", "application/pdf")},
            )

            timeline_after_upload = api_client.get(
                f"/api/core/client/documents/{document_id}/timeline",
                headers={"Authorization": f"Bearer {client_token}"},
            )
            uploaded_events = [item for item in timeline_after_upload.json() if item["event_type"] == "FILE_UPLOADED"]
            assert uploaded_events
            assert uploaded_events[0]["meta"]["filename"] == "_.pdf"
    finally:
        app.dependency_overrides.clear()
