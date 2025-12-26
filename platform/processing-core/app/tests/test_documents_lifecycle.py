from datetime import date

from fastapi.testclient import TestClient

import pytest

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client_actions import DocumentAcknowledgement
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services.document_chain import compute_ack_hash


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_document(session, *, status: DocumentStatus, doc_hash: str, version: int = 1) -> Document:
    document = Document(
        tenant_id=1,
        client_id="client-1",
        document_type=DocumentType.INVOICE,
        period_from=date(2025, 1, 1),
        period_to=date(2025, 1, 31),
        status=status,
        version=version,
    )
    session.add(document)
    session.flush()
    session.add(
        DocumentFile(
            document_id=document.id,
            file_type=DocumentFileType.PDF,
            bucket="docs",
            object_key=f"docs/{document.id}.pdf",
            sha256=doc_hash,
            size_bytes=100,
            content_type="application/pdf",
        )
    )
    session.commit()
    session.refresh(document)
    return document


def test_document_ack_hash_mismatch_returns_conflict(make_jwt):
    session = SessionLocal()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-2")
        session.add(
            DocumentAcknowledgement(
                tenant_id=1,
                client_id="client-1",
                document_type=DocumentType.INVOICE.value,
                document_id=str(document.id),
                document_object_key=f"docs/{document.id}.pdf",
                document_hash="hash-1",
                ack_by_user_id="user-1",
                ack_by_email="client@example.com",
                ack_method="UI",
            )
        )
        session.commit()
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            client_id="client-1",
            extra={"tenant_id": 1, "email": "client@example.com"},
        )

        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
            response = api_client.post(f"/api/v1/client/documents/{document.id}/ack")
            assert response.status_code == 409
    finally:
        session.close()


def test_document_ack_hash_reproducible(make_jwt):
    session = SessionLocal()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-1")
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            client_id="client-1",
            extra={"tenant_id": 1, "email": "client@example.com"},
        )

        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
            response = api_client.post(f"/api/v1/client/documents/{document.id}/ack")
            assert response.status_code == 201

        acknowledgement = (
            session.query(DocumentAcknowledgement)
            .filter(DocumentAcknowledgement.document_id == str(document.id))
            .one()
        )
        audit_entry = (
            session.query(AuditLog)
            .filter(AuditLog.event_type == "DOCUMENT_ACKNOWLEDGED")
            .filter(AuditLog.entity_id == str(document.id))
            .one()
        )
        ack_by = acknowledgement.ack_by_user_id or acknowledgement.ack_by_email or ""
        expected_hash = compute_ack_hash(acknowledgement.document_hash, acknowledgement.ack_at, ack_by)
        assert audit_entry.after["ack_hash"] == expected_hash
    finally:
        session.close()


def test_document_finalize_blocks_void(make_jwt):
    session = SessionLocal()
    try:
        session.add(
            RiskThresholdSet(
                id="document-global",
                subject_type=RiskSubjectType.DOCUMENT,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.DOCUMENT_FINALIZE,
                block_threshold=80,
                review_threshold=60,
                allow_threshold=10,
            )
        )
        session.commit()
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-1")
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            client_id="client-1",
            extra={"tenant_id": 1, "email": "client@example.com"},
        )
        admin_token = make_jwt(roles=("ADMIN", "ADMIN_FINANCE"))

        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
            response = api_client.post(f"/api/v1/client/documents/{document.id}/ack")
            assert response.status_code == 201

        with TestClient(app, headers={"Authorization": f"Bearer {admin_token}"}) as api_client:
            response = api_client.post(f"/api/v1/admin/documents/{document.id}/finalize")
            assert response.status_code == 200

            response = api_client.post(f"/api/v1/admin/documents/{document.id}/void")
            assert response.status_code == 409
    finally:
        session.close()


def test_document_list_links_to_details(make_jwt):
    session = SessionLocal()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-1")
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            client_id="client-1",
            extra={"tenant_id": 1, "email": "client@example.com"},
        )

        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
            listing = api_client.get("/api/v1/client/documents")
            assert listing.status_code == 200
            payload = listing.json()
            assert payload["total"] == 1
            assert payload["items"][0]["id"] == str(document.id)
            assert payload["items"][0]["pdf_hash"] == "hash-1"

            details = api_client.get(f"/api/v1/client/documents/{document.id}")
            assert details.status_code == 200
            detail_payload = details.json()
            assert detail_payload["id"] == str(document.id)
            assert detail_payload["document_hash"] == "hash-1"
    finally:
        session.close()


def test_document_ack_updates_status_and_audit_event(make_jwt):
    session = SessionLocal()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-1")
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            client_id="client-1",
            extra={"tenant_id": 1, "email": "client@example.com"},
        )

        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
            response = api_client.post(f"/api/v1/client/documents/{document.id}/ack")
            assert response.status_code == 201

        session.refresh(document)
        assert document.status == DocumentStatus.ACKNOWLEDGED
        assert document.ack_at is not None
        assert (
            session.query(AuditLog)
            .filter(AuditLog.event_type == "DOCUMENT_ACKNOWLEDGED")
            .filter(AuditLog.entity_id == str(document.id))
            .count()
            == 1
        )
    finally:
        session.close()


def test_void_acknowledged_document_returns_conflict(make_jwt):
    session = SessionLocal()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-1")
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            client_id="client-1",
            extra={"tenant_id": 1, "email": "client@example.com"},
        )
        admin_token = make_jwt(roles=("ADMIN", "ADMIN_FINANCE"))

        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
            response = api_client.post(f"/api/v1/client/documents/{document.id}/ack")
            assert response.status_code == 201

        with TestClient(app, headers={"Authorization": f"Bearer {admin_token}"}) as api_client:
            response = api_client.post(f"/api/v1/admin/documents/{document.id}/void")
            assert response.status_code == 409
    finally:
        session.close()
