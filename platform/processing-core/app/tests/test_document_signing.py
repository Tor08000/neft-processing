from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.audit_log import AuditLog
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.legal_integrations import DocumentSignature, DocumentSignatureStatus, SignatureType
from app.services.document_service_client import (
    DocumentServiceClient,
    DocumentSignResult,
    DocumentStorageRef,
    DocumentVerifyResult,
)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_document(session) -> Document:
    document = Document(
        tenant_id=1,
        client_id="client-1",
        document_type=DocumentType.INVOICE,
        period_from=date(2025, 1, 1),
        period_to=date(2025, 1, 31),
        status=DocumentStatus.ISSUED,
        version=1,
    )
    session.add(document)
    session.flush()
    session.add(
        DocumentFile(
            document_id=document.id,
            file_type=DocumentFileType.PDF,
            bucket="docs",
            object_key=f"documents/client-1/2025-01-01_2025-01-31/v1.pdf",
            sha256="doc-hash",
            size_bytes=100,
            content_type="application/pdf",
        )
    )
    session.commit()
    session.refresh(document)
    return document


def test_request_sign_success(monkeypatch, admin_auth_headers):
    session = SessionLocal()
    try:
        document = _seed_document(session)

        def fake_sign(self, request):
            return DocumentSignResult(
                status="SIGNED",
                provider_request_id="req-1",
                signed=DocumentStorageRef(
                    bucket="docs",
                    object_key="documents/client-1/2025-01-01_2025-01-31/v1.signed.pdf",
                    sha256="signed-hash",
                    size_bytes=200,
                ),
                signature=DocumentStorageRef(
                    bucket="docs",
                    object_key="documents/client-1/2025-01-01_2025-01-31/v1.sig.p7s",
                    sha256="sig-hash",
                    size_bytes=50,
                ),
                certificate={"subject": "CN=Test"},
            )

        monkeypatch.setattr(DocumentServiceClient, "sign", fake_sign)

        client = TestClient(app)
        response = client.post(
            f"/api/v1/admin/documents/{document.id}/sign/request",
            headers=admin_auth_headers,
            json={"provider": "provider_x", "meta": {"reason": "closing"}},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["signature"]["status"] == "SIGNED"

        signature = session.query(DocumentSignature).one()
        assert signature.status == DocumentSignatureStatus.SIGNED
        assert signature.signed_object_key.endswith("v1.signed.pdf")
        assert signature.signature_sha256 == "sig-hash"

        events = {row.event_type for row in session.query(AuditLog.event_type).all()}
        assert "DOCUMENT_SIGNING_REQUESTED" in events
        assert "DOCUMENT_SIGNED" in events
    finally:
        session.close()


def test_request_sign_failure(monkeypatch, admin_auth_headers):
    session = SessionLocal()
    try:
        document = _seed_document(session)

        def fake_sign(self, request):
            raise RuntimeError("provider_down")

        monkeypatch.setattr(DocumentServiceClient, "sign", fake_sign)

        client = TestClient(app)
        response = client.post(
            f"/api/v1/admin/documents/{document.id}/sign/request",
            headers=admin_auth_headers,
            json={"provider": "provider_x"},
        )

        assert response.status_code == 502

        signature = session.query(DocumentSignature).one()
        assert signature.status == DocumentSignatureStatus.FAILED

        events = {row.event_type for row in session.query(AuditLog.event_type).all()}
        assert "DOCUMENT_SIGN_FAILED" in events
    finally:
        session.close()


def test_verify_signature(monkeypatch, admin_auth_headers):
    session = SessionLocal()
    try:
        document = _seed_document(session)

        signature = DocumentSignature(
            document_id=document.id,
            provider="provider_x",
            version=1,
            status=DocumentSignatureStatus.SIGNED,
            input_object_key="documents/client-1/2025-01-01_2025-01-31/v1.pdf",
            input_sha256="doc-hash",
            signature_object_key="documents/client-1/2025-01-01_2025-01-31/v1.sig.p7s",
            signature_sha256="sig-hash",
            attempt=1,
            signature_type=SignatureType.ESIGN,
            signature_hash_sha256="sig-hash",
        )
        session.add(signature)
        session.commit()

        def fake_verify(self, request):
            return DocumentVerifyResult(status="VERIFIED", verified=True, error_code=None)

        monkeypatch.setattr(DocumentServiceClient, "verify", fake_verify)

        client = TestClient(app)
        response = client.post(
            f"/api/v1/admin/documents/{document.id}/signatures/{signature.id}/verify",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        session.refresh(signature)
        assert signature.status == DocumentSignatureStatus.VERIFIED
    finally:
        session.close()
