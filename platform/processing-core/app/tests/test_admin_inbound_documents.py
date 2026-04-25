from __future__ import annotations

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.client import client_portal_user
from app.domains.documents.models import Document, DocumentFile, DocumentTimelineEvent
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.service import DocumentsService
from app.routers.admin_documents_v1 import _service as admin_service_dep
from app.routers.admin_documents_v1 import router as admin_documents_router
from app.routers.client_documents_v1 import _service as client_service_dep
from app.routers.client_documents_v1 import router as client_documents_router
from app.tests._scoped_router_harness import router_client_context


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


def _override_service(db: Session, storage: _InMemoryStorage) -> DocumentsService:
    return DocumentsService(repo=DocumentsRepository(db=db), storage=storage)


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


def _documents_test_router() -> APIRouter:
    router = APIRouter()
    router.include_router(admin_documents_router)
    router.include_router(client_documents_router)
    return router


@pytest.fixture()
def db_session_factory() -> sessionmaker[Session]:
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

    try:
        yield testing_session_local
    finally:
        engine.dispose()


@pytest.fixture()
def db_session(db_session_factory) -> Session:
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


def _cleanup(db: Session) -> None:
    db.query(DocumentTimelineEvent).delete()
    db.query(DocumentFile).delete()
    db.query(Document).delete()
    db.commit()


def _documents_dependency_overrides(db: Session, storage: _InMemoryStorage, client_claims: dict):
    return {
        require_admin_user: lambda: {"roles": ["ADMIN"], "sub": "admin-1"},
        client_portal_user: lambda: client_claims,
        admin_service_dep: lambda: _override_service(db, storage),
        client_service_dep: lambda: _override_service(db, storage),
    }


def test_admin_create_inbound_document_success(make_jwt, db_session):
    _cleanup(db_session)
    storage = _InMemoryStorage()
    admin_token = make_jwt(roles=("ADMIN",))
    client_token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    client_claims = {"client_id": "client-a", "sub": "user-a"}

    with router_client_context(
        router=_documents_test_router(),
        db_session=db_session,
        dependency_overrides=_documents_dependency_overrides(db_session, storage, client_claims),
    ) as api_client:
        created = api_client.post(
            "/api/core/admin/clients/client-a/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "РђРєС‚ Р·Р° СЏРЅРІР°СЂСЊ",
                "category": "ACT",
                "description": "РђРєС‚",
                "attach_mode": "UPLOAD",
            },
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


def test_admin_attach_file_inbound_success(make_jwt, db_session):
    _cleanup(db_session)
    storage = _InMemoryStorage()
    admin_token = make_jwt(roles=("ADMIN",))
    client_token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    client_claims = {"client_id": "client-a", "sub": "user-a"}

    with router_client_context(
        router=_documents_test_router(),
        db_session=db_session,
        dependency_overrides=_documents_dependency_overrides(db_session, storage, client_claims),
    ) as api_client:
        created = api_client.post(
            "/api/core/admin/clients/client-a/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"title": "РђРєС‚ Р·Р° СЏРЅРІР°СЂСЊ", "category": "ACT", "attach_mode": "UPLOAD"},
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


def test_client_cannot_access_other_clients_inbound(make_jwt, db_session):
    _cleanup(db_session)
    storage = _InMemoryStorage()
    admin_token = make_jwt(roles=("ADMIN",))
    client_claims = {"client_id": "client-a", "sub": "user-a"}

    with router_client_context(
        router=_documents_test_router(),
        db_session=db_session,
        dependency_overrides=_documents_dependency_overrides(db_session, storage, client_claims),
    ) as api_client:
        created = api_client.post(
            "/api/core/admin/clients/client-b/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"title": "Р’С…РѕРґСЏС‰РёР№", "attach_mode": "UPLOAD"},
        )
        document_id = created.json()["id"]

        client_a_token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
        denied = api_client.get(
            f"/api/core/client/documents/{document_id}",
            headers={"Authorization": f"Bearer {client_a_token}"},
        )
        assert denied.status_code == 404


def test_timeline_created_and_file_uploaded(make_jwt, db_session):
    _cleanup(db_session)
    storage = _InMemoryStorage()
    admin_token = make_jwt(roles=("ADMIN",))
    client_token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    client_claims = {"client_id": "client-a", "sub": "user-a"}

    with router_client_context(
        router=_documents_test_router(),
        db_session=db_session,
        dependency_overrides=_documents_dependency_overrides(db_session, storage, client_claims),
    ) as api_client:
        created = api_client.post(
            "/api/core/admin/clients/client-a/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"title": "РђРєС‚ Р·Р° СЏРЅРІР°СЂСЊ", "attach_mode": "UPLOAD"},
        )
        document_id = created.json()["id"]

        timeline_after_create = api_client.get(
            f"/api/core/client/documents/{document_id}/timeline",
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert timeline_after_create.status_code == 200
        created_events = [
            item for item in timeline_after_create.json() if item["event_type"] == "DOCUMENT_CREATED"
        ]
        assert created_events

        api_client.post(
            f"/api/core/admin/documents/{document_id}/files",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("Р°РєС‚.pdf", b"timeline", "application/pdf")},
        )

        timeline_after_upload = api_client.get(
            f"/api/core/client/documents/{document_id}/timeline",
            headers={"Authorization": f"Bearer {client_token}"},
        )
        uploaded_events = [
            item for item in timeline_after_upload.json() if item["event_type"] == "FILE_UPLOADED"
        ]
        assert uploaded_events
        assert uploaded_events[0]["meta"]["filename"] == "_.pdf"
