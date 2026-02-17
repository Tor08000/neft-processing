from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.dependencies.client import client_portal_user
from app.domains.documents.models import Document, DocumentDirection, DocumentFile, DocumentSignature, DocumentStatus, DocumentTimelineEvent
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.service import DocumentsService
from app.main import app


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


def _cleanup(db):
    db.query(DocumentTimelineEvent).delete()
    db.query(DocumentSignature).delete()
    db.query(DocumentFile).delete()
    db.query(Document).delete()
    db.commit()


def _mk_doc(db, *, client_id: str = "client-a", direction: str = DocumentDirection.INBOUND.value, status: str = DocumentStatus.READY_TO_SIGN.value) -> str:
    item = Document(id="10000000-0000-0000-0000-000000000001", client_id=client_id, direction=direction, title="doc", status=status)
    db.add(item)
    db.commit()
    return str(item.id)


def _attach_file(db, document_id: str, storage_key: str = "s3://doc.pdf") -> None:
    db.add(
        DocumentFile(
            id="10000000-0000-0000-0000-000000000002",
            document_id=document_id,
            storage_key=storage_key,
            filename="doc.pdf",
            mime="application/pdf",
            size=4,
            sha256="",
        )
    )
    db.commit()


def _override_service(test_db_session, storage):
    service = DocumentsService(repo=DocumentsRepository(db=test_db_session), storage=storage)
    app.dependency_overrides.clear()
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a", "user_id": "20000000-0000-0000-0000-000000000001"}
    import app.routers.client_documents_v1 as router_module

    app.dependency_overrides[router_module._service] = lambda: service


def _sign(c: TestClient, doc_id: str, token: str):
    return c.post(
        f"/api/core/client/documents/{doc_id}/sign",
        json={"consent_text_version": "v1", "checkbox_confirmed": True, "signer_full_name": "Ivan Petrov"},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_sign_forbidden_for_other_client(make_jwt, test_db_session):
    _cleanup(test_db_session)
    doc_id = _mk_doc(test_db_session, client_id="client-b")
    _attach_file(test_db_session, doc_id)
    _override_service(test_db_session, _StorageStub({"s3://doc.pdf": b"pdf"}))
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            resp = _sign(c, doc_id, token)
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_sign_forbidden_for_outbound(make_jwt, test_db_session):
    _cleanup(test_db_session)
    doc_id = _mk_doc(test_db_session, direction=DocumentDirection.OUTBOUND.value)
    _attach_file(test_db_session, doc_id)
    _override_service(test_db_session, _StorageStub({"s3://doc.pdf": b"pdf"}))
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            resp = _sign(c, doc_id, token)
        assert resp.status_code == 409
        assert resp.json()["detail"] == "SIGN_NOT_ALLOWED_FOR_OUTBOUND"
    finally:
        app.dependency_overrides.clear()


def test_sign_requires_ready_status(make_jwt, test_db_session):
    _cleanup(test_db_session)
    doc_id = _mk_doc(test_db_session, status=DocumentStatus.DRAFT.value)
    _attach_file(test_db_session, doc_id)
    _override_service(test_db_session, _StorageStub({"s3://doc.pdf": b"pdf"}))
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            resp = _sign(c, doc_id, token)
        assert resp.status_code == 409
        assert resp.json()["detail"] == "DOC_NOT_READY_TO_SIGN"
    finally:
        app.dependency_overrides.clear()


def test_sign_creates_signature_and_updates_doc(make_jwt, test_db_session):
    _cleanup(test_db_session)
    doc_id = _mk_doc(test_db_session)
    _attach_file(test_db_session, doc_id)
    _override_service(test_db_session, _StorageStub({"s3://doc.pdf": b"pdf"}))
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            resp = _sign(c, doc_id, token)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == DocumentStatus.SIGNED_CLIENT.value

        sig_count = test_db_session.query(DocumentSignature).filter(DocumentSignature.document_id == doc_id).count()
        assert sig_count == 1
        doc = test_db_session.query(Document).filter(Document.id == doc_id).one()
        assert doc.status == DocumentStatus.SIGNED_CLIENT.value
        event = (
            test_db_session.query(DocumentTimelineEvent)
            .filter(DocumentTimelineEvent.document_id == doc_id)
            .filter(DocumentTimelineEvent.event_type == "SIGNED_CLIENT")
            .one_or_none()
        )
        assert event is not None
    finally:
        app.dependency_overrides.clear()


def test_sign_idempotent(make_jwt, test_db_session):
    _cleanup(test_db_session)
    doc_id = _mk_doc(test_db_session)
    _attach_file(test_db_session, doc_id)
    _override_service(test_db_session, _StorageStub({"s3://doc.pdf": b"pdf"}))
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            first = _sign(c, doc_id, token)
            second = _sign(c, doc_id, token)
        assert first.status_code == 200
        assert second.status_code == 200
        sig_count = test_db_session.query(DocumentSignature).filter(DocumentSignature.document_id == doc_id).count()
        assert sig_count == 1
    finally:
        app.dependency_overrides.clear()


def test_sign_fails_if_file_missing(make_jwt, test_db_session):
    _cleanup(test_db_session)
    doc_id = _mk_doc(test_db_session)
    _attach_file(test_db_session, doc_id, storage_key="s3://missing.pdf")
    _override_service(test_db_session, _StorageMissing())
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    try:
        with TestClient(app) as c:
            resp = _sign(c, doc_id, token)
        assert resp.status_code == 409
        assert resp.json()["detail"] == "DOC_FILE_MISSING"
    finally:
        app.dependency_overrides.clear()
