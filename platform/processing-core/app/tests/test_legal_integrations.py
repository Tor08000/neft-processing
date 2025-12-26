from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.client_actions import DocumentAcknowledgement
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.legal_integrations import (
    DocumentEnvelope,
    DocumentEnvelopeStatus,
    DocumentSignature,
    LegalProviderConfig,
)
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.main import app
from fastapi.testclient import TestClient
from app.services.decision.result import DecisionOutcome, DecisionResult
from app.services.legal_integrations.base import EnvelopeStatus
from app.services.legal_integrations.providers.noop import NoopLegalAdapter
from app.services.legal_integrations.registry import LegalAdapterRegistry
from app.services.legal_integrations.service import LegalIntegrationsService
from app.services.documents_storage import StoredDocumentFile


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


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_document(session, *, status: DocumentStatus) -> Document:
    document = Document(
        tenant_id=1,
        client_id="client-1",
        document_type=DocumentType.INVOICE,
        period_from=date(2025, 1, 1),
        period_to=date(2025, 1, 31),
        status=status,
        version=1,
    )
    session.add(document)
    session.flush()
    session.add(
        DocumentFile(
            document_id=document.id,
            file_type=DocumentFileType.PDF,
            bucket="docs",
            object_key=f"docs/{document.id}.pdf",
            sha256="doc-hash",
            size_bytes=100,
            content_type="application/pdf",
        )
    )
    session.commit()
    session.refresh(document)
    return document


def test_adapter_registry_selects_provider():
    registry = LegalAdapterRegistry()
    adapter = NoopLegalAdapter()
    registry.register(adapter)
    assert registry.get("noop") is adapter


def test_envelope_persistence_idempotent():
    session = SessionLocal()
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
    session = SessionLocal()
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
        assert session.query(DocumentSignature).count() == 1
    finally:
        session.close()


def test_risk_block_enforced():
    session = SessionLocal()
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


def test_noop_flow_allows_finalize(make_jwt):
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

        admin_token = make_jwt(roles=("ADMIN", "ADMIN_FINANCE"))
        with TestClient(app, headers={"Authorization": f"Bearer {admin_token}"}) as api_client:
            response = api_client.post(f"/api/v1/admin/documents/{document.id}/finalize")
            assert response.status_code == 200
    finally:
        session.close()
