from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient

import pytest
from sqlalchemy import Column, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as app_main
from app.db import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client_actions import DocumentAcknowledgement
from app.models.decision_result import DecisionResult
from app.models.documents import (
    ClosingPackage,
    ClosingPackageStatus,
    Document,
    DocumentFile,
    DocumentFileType,
    DocumentStatus,
    DocumentType,
)
from app.models.legal_integrations import Certificate, DocumentSignature, LegalProviderConfig
from app.models.risk_decision import RiskDecision
from app.models.risk_threshold_set import RiskThresholdSet
from app.services.decision.result import DecisionOutcome, DecisionResult as DecisionServiceResult
from app.services.document_chain import compute_ack_hash


def _dedupe_table_indexes(*tables) -> None:
    for table in tables:
        seen: set[tuple[str | None, tuple[str, ...]]] = set()
        for index in list(table.indexes):
            signature = (index.name, tuple(column.name for column in index.columns))
            if signature in seen:
                table.indexes.remove(index)
            else:
                seen.add(signature)


class _AllowAllDecisionEngine:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def evaluate(self, _ctx):
        return DecisionServiceResult(
            decision_id="documents-lifecycle",
            decision_version="v1",
            outcome=DecisionOutcome.ALLOW,
            risk_score=0,
            explain={"stub": True},
        )


class _NoopGraphBuilder:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def ensure_document_graph(self, *args, **kwargs) -> None:
        return None

    def ensure_document_ack_graph(self, *args, **kwargs) -> None:
        return None


class _NoopGraphSnapshotService:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def create_snapshot(self, *args, **kwargs) -> None:
        return None


@pytest.fixture()
def db_session_factory(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    import app.routers.admin.documents as admin_documents_router
    import app.routers.client_documents as client_documents_router

    monkeypatch.setattr(app_main.settings, "APP_ENV", "dev", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    monkeypatch.setattr(admin_documents_router, "DecisionEngine", _AllowAllDecisionEngine)
    monkeypatch.setattr(admin_documents_router, "LegalGraphBuilder", _NoopGraphBuilder)
    monkeypatch.setattr(admin_documents_router, "LegalGraphSnapshotService", _NoopGraphSnapshotService)
    monkeypatch.setattr(client_documents_router, "LegalGraphBuilder", _NoopGraphBuilder)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if "users" not in Base.metadata.tables:
        Table("users", Base.metadata, Column("id", String(64), primary_key=True), extend_existing=True)

    _dedupe_table_indexes(DocumentFile.__table__, DocumentSignature.__table__)

    Base.metadata.create_all(
        bind=engine,
        tables=[
            Document.__table__,
            DocumentFile.__table__,
            ClosingPackage.__table__,
            DocumentAcknowledgement.__table__,
            AuditLog.__table__,
            RiskThresholdSet.__table__,
            LegalProviderConfig.__table__,
            Certificate.__table__,
            DocumentSignature.__table__,
            RiskDecision.__table__,
            DecisionResult.__table__,
        ],
    )

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


def _seed_document(session: Session, *, status: DocumentStatus, doc_hash: str, version: int = 1) -> Document:
    document = Document(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        direction="INBOUND",
        title="Invoice",
        document_type=DocumentType.INVOICE,
        period_from=date(2025, 1, 1),
        period_to=date(2025, 1, 31),
        status=status,
        sender_type="NEFT",
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


def _seed_closing_package(session: Session, *, status: ClosingPackageStatus) -> ClosingPackage:
    package = ClosingPackage(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        period_from=date(2025, 1, 1),
        period_to=date(2025, 1, 31),
        status=status,
        version=1,
    )
    session.add(package)
    session.commit()
    session.refresh(package)
    return package


def test_document_ack_hash_mismatch_returns_conflict(make_jwt, db_session_factory):
    session = db_session_factory()
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
            extra={"tenant_id": 1, "email": "client@example.com", "aud": "neft-client"},
        )

        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
            response = api_client.post(f"/api/v1/client/documents/{document.id}/ack")
            assert response.status_code == 409
    finally:
        session.close()


def test_document_ack_hash_reproducible(make_jwt, db_session_factory):
    session = db_session_factory()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-1")
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            client_id="client-1",
            extra={"tenant_id": 1, "email": "client@example.com", "aud": "neft-client"},
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


def test_document_ack_uses_document_tenant_when_token_tenant_is_uuid(make_jwt, db_session_factory):
    session = db_session_factory()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-uuid")
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            sub="client@neft.local",
            client_id="client-1",
            extra={
                "tenant_id": "aaf19bab-c7ac-4cbf-9ad3-1d515fc6fb2c",
                "aud": "neft-client",
            },
        )

        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
            response = api_client.post(f"/api/v1/client/documents/{document.id}/ack")
            assert response.status_code == 201

        acknowledgement = (
            session.query(DocumentAcknowledgement)
            .filter(DocumentAcknowledgement.document_id == str(document.id))
            .one()
        )
        session.refresh(document)
        assert acknowledgement.tenant_id == document.tenant_id == 1
        assert document.status == DocumentStatus.ACKNOWLEDGED
    finally:
        session.close()


def test_closing_package_ack_uses_package_tenant_when_token_tenant_is_uuid(make_jwt, db_session_factory):
    session = db_session_factory()
    try:
        package = _seed_closing_package(session, status=ClosingPackageStatus.ISSUED)
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            sub="client@neft.local",
            client_id="client-1",
            extra={
                "tenant_id": "aaf19bab-c7ac-4cbf-9ad3-1d515fc6fb2c",
                "aud": "neft-client",
            },
        )

        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
            response = api_client.post(f"/api/v1/client/closing-packages/{package.id}/ack")
            assert response.status_code == 200

        session.refresh(package)
        assert package.status == ClosingPackageStatus.ACKNOWLEDGED
        assert package.ack_at is not None
        assert (
            session.query(AuditLog)
            .filter(AuditLog.event_type == "CLOSING_PACKAGE_ACKNOWLEDGED")
            .filter(AuditLog.entity_id == str(package.id))
            .count()
            == 1
        )
    finally:
        session.close()


def test_document_finalize_blocks_void(make_jwt, db_session_factory):
    session = db_session_factory()
    try:
        session.add(
            RiskThresholdSet(
                id="document-global",
                subject_type="DOCUMENT",
                scope="GLOBAL",
                action="DOCUMENT_FINALIZE",
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
            extra={"tenant_id": 1, "email": "client@example.com", "aud": "neft-client"},
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


def test_document_list_links_to_details(make_jwt, db_session_factory):
    session = db_session_factory()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-1")
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            client_id="client-1",
            extra={"tenant_id": 1, "email": "client@example.com", "aud": "neft-client"},
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


def test_document_ack_updates_status_and_audit_event(make_jwt, db_session_factory):
    session = db_session_factory()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-1")
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            client_id="client-1",
            extra={"tenant_id": 1, "email": "client@example.com", "aud": "neft-client"},
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


def test_void_acknowledged_document_returns_conflict(make_jwt, db_session_factory):
    session = db_session_factory()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED, doc_hash="hash-1")
        token = make_jwt(
            roles=("CLIENT_OWNER",),
            client_id="client-1",
            extra={"tenant_id": 1, "email": "client@example.com", "aud": "neft-client"},
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
