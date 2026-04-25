from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Enum as SAEnum, Integer, MetaData, String, Text, text
from sqlalchemy.orm import declarative_base

import app.db as db_module
from app.models.client_actions import DocumentAcknowledgement
from app.models.documents import DocumentFileType, DocumentStatus, DocumentType
from app.models.legal_integrations import (
    DocumentEnvelope,
    DocumentEnvelopeStatus,
    DocumentSignature,
    LegalProviderConfig,
)
from app.services.decision.result import DecisionOutcome, DecisionResult
from app.services.documents_storage import StoredDocumentFile
from app.services.legal_integrations.base import EnvelopeStatus
from app.services.legal_integrations.errors import ProviderNotConfigured
from app.services.legal_integrations.providers.noop import NoopLegalAdapter
from app.services.legal_integrations.registry import LegalAdapterRegistry
from app.services.legal_integrations.service import LegalIntegrationsService


LegalTestBase = declarative_base(metadata=MetaData())


class LegalTestDocumentRecord(LegalTestBase):
    __tablename__ = "documents"
    __test__ = False

    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    document_type = Column(SAEnum(DocumentType, native_enum=False), nullable=False)
    period_from = Column(Date, nullable=False)
    period_to = Column(Date, nullable=False)
    status = Column(SAEnum(DocumentStatus, native_enum=False), nullable=False)
    version = Column(Integer, nullable=False)
    number = Column(Text, nullable=True)
    source_entity_type = Column(Text, nullable=True)
    source_entity_id = Column(Text, nullable=True)
    document_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    ack_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_by_actor_type = Column(String(32), nullable=True)
    created_by_actor_id = Column(Text, nullable=True)
    created_by_email = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)


class LegalTestFileRecord(LegalTestBase):
    __tablename__ = "document_files"
    __test__ = False

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(String(36), nullable=False, index=True)
    file_type = Column(String(32), nullable=False)
    bucket = Column(Text, nullable=False)
    object_key = Column(Text, nullable=False)
    sha256 = Column(String(64), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_type = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    meta = Column(JSON, nullable=True)


class LegalTestSignatureRecord(LegalTestBase):
    __tablename__ = "document_signatures"
    __test__ = False

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    request_id = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False)
    input_object_key = Column(Text, nullable=True)
    input_sha256 = Column(String(64), nullable=True)
    signed_object_key = Column(Text, nullable=True)
    signed_sha256 = Column(String(64), nullable=True)
    signature_object_key = Column(Text, nullable=True)
    signature_sha256 = Column(String(64), nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    error_code = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON, nullable=True)
    signature_type = Column(String(32), nullable=False)
    file_id = Column(String(36), nullable=True)
    signature_hash_sha256 = Column(String(64), nullable=False)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    certificate_id = Column(String(36), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)
    verification_details = Column(JSON, nullable=True)


class StubDecisionEngine:
    def __init__(self, outcome: DecisionOutcome) -> None:
        self.outcome = outcome

    def evaluate(self, _ctx):
        return DecisionResult(
            decision_id="test",
            decision_version="v1",
            outcome=self.outcome,
            risk_score=0,
            explain={"stub": True},
        )


class StubStorage:
    def __init__(self):
        self.payloads: dict[str, bytes] = {}

    def store_bytes(self, *, object_key: str, payload: bytes, content_type: str):
        self.payloads[object_key] = payload
        return StoredDocumentFile(
            bucket="stub",
            object_key=object_key,
            sha256="stub-hash",
            size_bytes=len(payload),
            content_type=content_type,
        )


class _NoopAckGraphBuilder:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def ensure_document_ack_graph(self, *args, **kwargs) -> None:
        return None


class _NoopDocumentGraphBuilder:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def ensure_document_graph(self, *args, **kwargs) -> None:
        return None


class _NoopGraphSnapshotService:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def create_snapshot(self, *args, **kwargs) -> None:
        return None


class _AllowAllDecisionEngine:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def evaluate(self, _ctx):
        return DecisionResult(
            decision_id="route-test",
            decision_version="v1",
            outcome=DecisionOutcome.ALLOW,
            risk_score=0,
            explain={"stub": True},
        )


def _create_minimal_legal_schema(engine) -> None:
    ddl = [
        """
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            client_id TEXT NOT NULL,
            document_type TEXT NOT NULL,
            period_from DATE NOT NULL,
            period_to DATE NOT NULL,
            status TEXT NOT NULL,
            version INTEGER NOT NULL,
            number TEXT,
            source_entity_type TEXT,
            source_entity_id TEXT,
            document_hash TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            generated_at DATETIME,
            sent_at DATETIME,
            ack_at DATETIME,
            cancelled_at DATETIME,
            created_by_actor_type TEXT,
            created_by_actor_id TEXT,
            created_by_email TEXT,
            meta TEXT
        )
        """,
        """
        CREATE TABLE document_files (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            bucket TEXT NOT NULL,
            object_key TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes BIGINT NOT NULL,
            content_type TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            meta TEXT,
            UNIQUE(document_id, file_type)
        )
        """,
        """
        CREATE TABLE legal_provider_configs (
            id TEXT PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            client_id TEXT NOT NULL,
            signing_provider TEXT NOT NULL,
            edo_provider TEXT NOT NULL,
            require_signature_for_finalize BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            UNIQUE(tenant_id, client_id)
        )
        """,
        """
        CREATE TABLE document_envelopes (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            envelope_id TEXT NOT NULL,
            status TEXT NOT NULL,
            sent_at DATETIME,
            last_status_at DATETIME,
            error_message TEXT,
            meta TEXT,
            UNIQUE(provider, envelope_id)
        )
        """,
        """
        CREATE TABLE document_signatures (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            request_id TEXT,
            status TEXT NOT NULL,
            input_object_key TEXT,
            input_sha256 TEXT,
            signed_object_key TEXT,
            signed_sha256 TEXT,
            signature_object_key TEXT,
            signature_sha256 TEXT,
            attempt INTEGER NOT NULL DEFAULT 1,
            error_code TEXT,
            error_message TEXT,
            started_at DATETIME,
            finished_at DATETIME,
            meta TEXT,
            signature_type TEXT NOT NULL,
            file_id TEXT,
            signature_hash_sha256 TEXT NOT NULL,
            signed_at DATETIME,
            certificate_id TEXT,
            verified BOOLEAN NOT NULL DEFAULT 0,
            verification_details TEXT
        )
        """,
        """
        CREATE TABLE document_acknowledgements (
            id TEXT PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            client_id TEXT NOT NULL,
            document_type TEXT NOT NULL,
            document_id TEXT NOT NULL,
            document_object_key TEXT,
            document_hash TEXT,
            ack_by_user_id TEXT,
            ack_by_email TEXT,
            ack_ip TEXT,
            ack_user_agent TEXT,
            ack_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            ack_method TEXT,
            UNIQUE(client_id, document_type, document_id)
        )
        """,
        """
        CREATE TABLE audit_log (
            id TEXT PRIMARY KEY,
            ts DATETIME NOT NULL,
            tenant_id INTEGER,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            actor_email TEXT,
            actor_roles TEXT,
            ip TEXT,
            user_agent TEXT,
            request_id TEXT,
            trace_id TEXT,
            event_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            visibility TEXT NOT NULL,
            before TEXT,
            after TEXT,
            diff TEXT,
            external_refs TEXT,
            reason TEXT,
            attachment_key TEXT,
            prev_hash TEXT NOT NULL,
            hash TEXT NOT NULL
        )
        """,
    ]
    with engine.begin() as conn:
        for statement in ddl:
            conn.exec_driver_sql(statement)


@pytest.fixture(autouse=True)
def isolated_legal_db(monkeypatch):
    db_url = "sqlite+pysqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    monkeypatch.setattr(db_module, "DATABASE_URL", db_url)
    db_module.reset_engine()
    _create_minimal_legal_schema(db_module.get_engine())

    import app.services.legal_integrations.service as legal_service_module

    monkeypatch.setattr(legal_service_module, "Document", LegalTestDocumentRecord)
    monkeypatch.setattr(legal_service_module, "DocumentFile", LegalTestFileRecord)
    monkeypatch.setattr(legal_service_module, "DocumentSignature", LegalTestSignatureRecord)
    monkeypatch.setattr(legal_service_module, "LegalGraphBuilder", _NoopAckGraphBuilder)
    monkeypatch.setattr(legal_service_module, "audit_graph_write_failure", lambda *args, **kwargs: None)
    yield
    db_module.reset_engine()


def _seed_document(session, *, status: DocumentStatus) -> LegalTestDocumentRecord:
    document_id = "00000000-0000-0000-0000-000000000401"
    file_id = "00000000-0000-0000-0000-000000000402"
    session.execute(
        text(
            """
            INSERT INTO documents (
                id, tenant_id, client_id, document_type, period_from, period_to, status, version
            ) VALUES (
                :id, :tenant_id, :client_id, :document_type, :period_from, :period_to, :status, :version
            )
            """
        ),
        {
            "id": document_id,
            "tenant_id": 1,
            "client_id": "client-1",
            "document_type": DocumentType.INVOICE.value,
            "period_from": date(2025, 1, 1),
            "period_to": date(2025, 1, 31),
            "status": status.value,
            "version": 1,
        },
    )
    session.execute(
        text(
            """
            INSERT INTO document_files (
                id, document_id, file_type, bucket, object_key, sha256, size_bytes, content_type
            ) VALUES (
                :id, :document_id, :file_type, :bucket, :object_key, :sha256, :size_bytes, :content_type
            )
            """
        ),
        {
            "id": file_id,
            "document_id": document_id,
            "file_type": DocumentFileType.PDF.value,
            "bucket": "docs",
            "object_key": f"docs/{document_id}.pdf",
            "sha256": "doc-hash",
            "size_bytes": 100,
            "content_type": "application/pdf",
        },
    )
    session.commit()
    return session.query(LegalTestDocumentRecord).filter(LegalTestDocumentRecord.id == document_id).one()


def test_adapter_registry_selects_provider():
    registry = LegalAdapterRegistry()
    adapter = NoopLegalAdapter()
    registry.register(adapter)
    assert registry.get("noop") is adapter


def test_placeholder_provider_config_fails_as_unconfigured():
    session = db_module.get_sessionmaker()()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED)
        session.add(
            LegalProviderConfig(
                tenant_id=1,
                client_id="client-1",
                signing_provider="docusign",
                edo_provider="none",
                require_signature_for_finalize=False,
            )
        )
        session.commit()

        registry = LegalAdapterRegistry()
        service = LegalIntegrationsService(
            session,
            registry=registry,
            decision_engine=StubDecisionEngine(DecisionOutcome.ALLOW),
            storage=StubStorage(),
        )
        token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1}
        with pytest.raises(ProviderNotConfigured, match="adapter_not_registered:docusign"):
            service.send_document_for_signing(document_id=str(document.id), token=token)
    finally:
        session.close()


def test_noop_provider_is_not_auto_registered_in_runtime():
    session = db_module.get_sessionmaker()()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED)
        session.add(
            LegalProviderConfig(
                tenant_id=1,
                client_id="client-1",
                signing_provider="noop",
                edo_provider="none",
                require_signature_for_finalize=False,
            )
        )
        session.commit()

        service = LegalIntegrationsService(
            session,
            registry=LegalAdapterRegistry(),
            decision_engine=StubDecisionEngine(DecisionOutcome.ALLOW),
            storage=StubStorage(),
        )
        token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1}
        with pytest.raises(ProviderNotConfigured, match="adapter_not_registered:noop"):
            service.send_document_for_signing(document_id=str(document.id), token=token)
    finally:
        session.close()


def test_envelope_persistence_idempotent():
    session = db_module.get_sessionmaker()()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED)
        session.add(
            LegalProviderConfig(
                tenant_id=1,
                client_id="client-1",
                signing_provider="noop",
                edo_provider="none",
                require_signature_for_finalize=False,
            )
        )
        session.commit()

        registry = LegalAdapterRegistry()
        registry.register(NoopLegalAdapter())
        service = LegalIntegrationsService(
            session,
            registry=registry,
            decision_engine=StubDecisionEngine(DecisionOutcome.ALLOW),
            storage=StubStorage(),
        )
        token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1}
        service.send_document_for_signing(document_id=str(document.id), token=token)
        service.send_document_for_signing(document_id=str(document.id), token=token)

        assert session.query(DocumentEnvelope).count() == 1
    finally:
        session.close()


def test_signature_artifacts_create_acknowledgement():
    session = db_module.get_sessionmaker()()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED)
        session.add(
            LegalProviderConfig(
                tenant_id=1,
                client_id="client-1",
                signing_provider="noop",
                edo_provider="none",
                require_signature_for_finalize=True,
            )
        )
        session.commit()

        registry = LegalAdapterRegistry()
        registry.register(NoopLegalAdapter())
        service = LegalIntegrationsService(
            session,
            registry=registry,
            decision_engine=StubDecisionEngine(DecisionOutcome.ALLOW),
            storage=StubStorage(),
        )
        token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1}
        envelope = service.send_document_for_signing(document_id=str(document.id), token=token)
        status = EnvelopeStatus(
            provider="noop",
            envelope_id=envelope.envelope_id,
            status=DocumentEnvelopeStatus.SIGNED,
            status_at=datetime.now(timezone.utc),
        )
        service.update_envelope_status(provider="noop", envelope_id=envelope.envelope_id, status=status)

        session.refresh(document)
        assert document.status == DocumentStatus.ACKNOWLEDGED
        assert session.query(DocumentAcknowledgement).count() == 1
        assert session.query(LegalTestSignatureRecord).count() == 1
    finally:
        session.close()


def test_risk_block_enforced():
    session = db_module.get_sessionmaker()()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED)
        session.add(
            LegalProviderConfig(
                tenant_id=1,
                client_id="client-1",
                signing_provider="noop",
                edo_provider="none",
                require_signature_for_finalize=False,
            )
        )
        session.commit()

        registry = LegalAdapterRegistry()
        registry.register(NoopLegalAdapter())
        service = LegalIntegrationsService(
            session,
            registry=registry,
            decision_engine=StubDecisionEngine(DecisionOutcome.DECLINE),
            storage=StubStorage(),
        )
        token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1}
        with pytest.raises(PermissionError):
            service.send_document_for_signing(document_id=str(document.id), token=token)
    finally:
        session.close()


def test_noop_flow_allows_finalize(make_jwt, monkeypatch):
    session = db_module.get_sessionmaker()()
    try:
        document = _seed_document(session, status=DocumentStatus.ISSUED)
        session.add(
            LegalProviderConfig(
                tenant_id=1,
                client_id="client-1",
                signing_provider="noop",
                edo_provider="none",
                require_signature_for_finalize=True,
            )
        )
        session.commit()

        registry = LegalAdapterRegistry()
        registry.register(NoopLegalAdapter())
        service = LegalIntegrationsService(
            session,
            registry=registry,
            decision_engine=StubDecisionEngine(DecisionOutcome.ALLOW),
            storage=StubStorage(),
        )
        token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1}
        envelope = service.send_document_for_signing(document_id=str(document.id), token=token)
        status = EnvelopeStatus(
            provider="noop",
            envelope_id=envelope.envelope_id,
            status=DocumentEnvelopeStatus.SIGNED,
            status_at=datetime.now(timezone.utc),
        )
        service.update_envelope_status(provider="noop", envelope_id=envelope.envelope_id, status=status)

        import app.routers.admin.documents as admin_documents_router
        from app.main import app

        monkeypatch.setattr(admin_documents_router, "Document", LegalTestDocumentRecord)
        monkeypatch.setattr(admin_documents_router, "DocumentFile", LegalTestFileRecord)
        monkeypatch.setattr(admin_documents_router, "DocumentSignature", LegalTestSignatureRecord)
        monkeypatch.setattr(admin_documents_router, "DecisionEngine", _AllowAllDecisionEngine)
        monkeypatch.setattr(admin_documents_router, "LegalGraphBuilder", _NoopDocumentGraphBuilder)
        monkeypatch.setattr(admin_documents_router, "LegalGraphSnapshotService", _NoopGraphSnapshotService)

        admin_token = make_jwt(roles=("ADMIN", "ADMIN_FINANCE"))
        with TestClient(app, headers={"Authorization": f"Bearer {admin_token}"}) as api_client:
            response = api_client.post(f"/api/v1/admin/documents/{document.id}/finalize")
            assert response.status_code == 200
    finally:
        session.close()
