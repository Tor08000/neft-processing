from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.dependencies.client import client_portal_user
from app.domains.documents.models import Document, DocumentDirection, DocumentEdoState, DocumentStatus
from app.main import app


def _cleanup(db) -> None:
    db.query(DocumentEdoState).delete()
    db.query(Document).delete()
    db.commit()


def _create_doc(db, *, status: str, direction: str = DocumentDirection.OUTBOUND.value) -> str:
    item = Document(
        id="00000000-0000-0000-0000-000000000123",
        client_id="client-a",
        direction=direction,
        title="doc",
        status=status,
    )
    db.add(item)
    db.commit()
    return str(item.id)


def _attach_file(db, document_id: str) -> None:
    db.execute(
        """
        insert into document_files (id, document_id, storage_key, filename, mime, size, sha256)
        values ('00000000-0000-0000-0000-000000000124', :document_id, 's3://k', 'a.pdf', 'application/pdf', 1, 'abc')
        """,
        {"document_id": document_id},
    )
    db.commit()


def test_send_requires_ready_to_send(make_jwt, test_db_session, monkeypatch):
    _cleanup(test_db_session)
    doc_id = _create_doc(test_db_session, status=DocumentStatus.DRAFT.value)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "mock")
    try:
        with TestClient(app) as c:
            resp = c.post(f"/api/core/client/documents/{doc_id}/send", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 409
        assert resp.json()["detail"]["error_code"] == "DOC_NOT_READY"
    finally:
        app.dependency_overrides.clear()


def test_send_requires_files(make_jwt, test_db_session, monkeypatch):
    _cleanup(test_db_session)
    doc_id = _create_doc(test_db_session, status=DocumentStatus.READY_TO_SEND.value)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "mock")
    try:
        with TestClient(app) as c:
            resp = c.post(f"/api/core/client/documents/{doc_id}/send", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 409
        assert resp.json()["detail"]["error_code"] == "DOC_FILES_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def test_prod_blocks_mock_or_missing_provider(make_jwt, test_db_session, monkeypatch):
    _cleanup(test_db_session)
    doc_id = _create_doc(test_db_session, status=DocumentStatus.READY_TO_SEND.value)
    _attach_file(test_db_session, doc_id)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "")
    try:
        with TestClient(app) as c:
            resp = c.post(f"/api/core/client/documents/{doc_id}/send", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in {409, 422}
        assert resp.json()["detail"]["error_code"] == "EDO_NOT_CONFIGURED"
    finally:
        app.dependency_overrides.clear()


def test_dev_allows_mock_send_creates_edostate(make_jwt, test_db_session, monkeypatch):
    _cleanup(test_db_session)
    doc_id = _create_doc(test_db_session, status=DocumentStatus.READY_TO_SEND.value)
    _attach_file(test_db_session, doc_id)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "mock")

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"edo_message_id": "m-1", "edo_status": "QUEUED", "provider": "mock", "provider_mode": "mock"}

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


def test_send_idempotent_returns_existing_state(make_jwt, test_db_session, monkeypatch):
    _cleanup(test_db_session)
    doc_id = _create_doc(test_db_session, status=DocumentStatus.READY_TO_SEND.value)
    _attach_file(test_db_session, doc_id)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("EDO_MODE", "mock")
    monkeypatch.setenv("EDO_PROVIDER", "mock")

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"edo_message_id": "same-1", "edo_status": "SENT", "provider": "mock", "provider_mode": "mock"}

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
