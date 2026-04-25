from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.main import app
from app.domains.documents.models import Document, DocumentDirection, DocumentEdoState, DocumentFile, DocumentStatus, DocumentTimelineEvent


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

    for table in _clone_tables_without_duplicate_indexes(
        Document.__table__,
        DocumentFile.__table__,
        DocumentTimelineEvent.__table__,
        DocumentEdoState.__table__,
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
        db.query(DocumentEdoState).delete()
        db.query(DocumentTimelineEvent).delete()
        db.query(DocumentFile).delete()
        db.query(Document).delete()
        db.commit()


def _create_doc(
    db_session_factory: sessionmaker[Session],
    *,
    status: str,
    direction: str = DocumentDirection.OUTBOUND.value,
) -> str:
    with db_session_factory() as db:
        item = Document(
            id="00000000-0000-0000-0000-000000000123",
            tenant_id=0,
            client_id="client-a",
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
    return "00000000-0000-0000-0000-000000000123"


def _attach_file(db_session_factory: sessionmaker[Session], document_id: str) -> None:
    with db_session_factory() as db:
        db.execute(
            text(
                """
                insert into document_files (
                    id, document_id, file_type, bucket, object_key, storage_key, filename, mime, size, size_bytes, content_type, sha256
                )
                values (
                    '00000000-0000-0000-0000-000000000124',
                    :document_id,
                    'PDF',
                    'client-documents',
                    's3://k',
                    's3://k',
                    'a.pdf',
                    'application/pdf',
                    1,
                    1,
                    'application/pdf',
                    'abc'
                )
                """
            ),
            {"document_id": document_id},
        )
        db.commit()


def test_send_requires_ready_to_send(make_jwt, db_session_factory, monkeypatch):
    _cleanup(db_session_factory)
    doc_id = _create_doc(db_session_factory, status=DocumentStatus.DRAFT.value)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "diadok")
    try:
        with TestClient(app) as c:
            resp = c.post(f"/api/core/client/documents/{doc_id}/send", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 409
        body = resp.json()
        assert body["detail"]["error_code"] == "DOC_NOT_READY"
    finally:
        app.dependency_overrides.clear()

def test_send_requires_files(make_jwt, db_session_factory, monkeypatch):
    _cleanup(db_session_factory)
    doc_id = _create_doc(db_session_factory, status=DocumentStatus.READY_TO_SEND.value)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "diadok")
    try:
        with TestClient(app) as c:
            resp = c.post(f"/api/core/client/documents/{doc_id}/send", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 409
        body = resp.json()
        assert body["detail"]["error_code"] == "DOC_FILES_REQUIRED"
    finally:
        app.dependency_overrides.clear()

def test_prod_blocks_mock_or_missing_provider(make_jwt, db_session_factory, monkeypatch):
    _cleanup(db_session_factory)
    doc_id = _create_doc(db_session_factory, status=DocumentStatus.READY_TO_SEND.value)
    _attach_file(db_session_factory, doc_id)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "")
    try:
        with TestClient(app) as c:
            resp = c.post(f"/api/core/client/documents/{doc_id}/send", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in {409, 422}
        body = resp.json()
        assert body["detail"]["error_code"] == "EDO_NOT_CONFIGURED"
    finally:
        app.dependency_overrides.clear()

def test_dev_requires_explicit_provider_configuration(make_jwt, db_session_factory, monkeypatch):
    _cleanup(db_session_factory)
    doc_id = _create_doc(db_session_factory, status=DocumentStatus.READY_TO_SEND.value)
    _attach_file(db_session_factory, doc_id)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "")
    try:
        with TestClient(app) as c:
            resp = c.post(f"/api/core/client/documents/{doc_id}/send", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["detail"]["error_code"] == "EDO_NOT_CONFIGURED"
    finally:
        app.dependency_overrides.clear()


def test_dev_allows_mock_send_creates_edostate(make_jwt, db_session_factory, monkeypatch):
    _cleanup(db_session_factory)
    doc_id = _create_doc(db_session_factory, status=DocumentStatus.READY_TO_SEND.value)
    _attach_file(db_session_factory, doc_id)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "diadok")

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"edo_message_id": "m-1", "edo_status": "QUEUED", "provider": "diadok", "provider_mode": "mock"}

    import app.domains.documents.edo_service as edo_module

    monkeypatch.setattr(edo_module.requests, "post", lambda *a, **k: _Resp())

    try:
        with TestClient(app) as c:
            resp = c.post(f"/api/core/client/documents/{doc_id}/send", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider_mode"] == "mock"
        assert body["edo_message_id"] == "m-1"
    finally:
        app.dependency_overrides.clear()


def test_send_idempotent_returns_existing_state(make_jwt, db_session_factory, monkeypatch):
    _cleanup(db_session_factory)
    doc_id = _create_doc(db_session_factory, status=DocumentStatus.READY_TO_SEND.value)
    _attach_file(db_session_factory, doc_id)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "diadok")

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"edo_message_id": "same-1", "edo_status": "SENT", "provider": "diadok", "provider_mode": "mock"}

    import app.domains.documents.edo_service as edo_module

    calls = {"post": 0}

    def _post(*a, **k):
        calls["post"] += 1
        return _Resp()

    monkeypatch.setattr(edo_module.requests, "post", _post)

    try:
        with TestClient(app) as c:
            first = c.post(f"/api/core/client/documents/{doc_id}/send", headers={"Authorization": f"Bearer {token}"})
            second = c.post(f"/api/core/client/documents/{doc_id}/send", headers={"Authorization": f"Bearer {token}"})
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["edo_message_id"] == second.json()["edo_message_id"]
        assert calls["post"] == 1
    finally:
        app.dependency_overrides.clear()
