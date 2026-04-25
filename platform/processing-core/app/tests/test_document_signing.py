from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, Integer, JSON, MetaData, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.audit_log import AuditLog
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.legal_integrations import DocumentSignatureStatus, SignatureType
from app.services.document_service_client import (
    DocumentSignResult,
    DocumentStorageRef,
    DocumentVerifyResult,
)
from app.services.document_signing import DocumentSigningService


ADMIN_TOKEN = {
    "user_id": "admin-1",
    "email": "admin@example.com",
    "roles": ["ADMIN", "ADMIN_FINANCE"],
    "tenant_id": 1,
}

SigningBase = declarative_base(metadata=MetaData())


class SigningSignatureRecord(SigningBase):
    __tablename__ = "document_signatures"
    __test__ = False

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    request_id = Column(String(128), nullable=True)
    status = Column(SAEnum(DocumentSignatureStatus, native_enum=False), nullable=False)
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
    signature_type = Column(SAEnum(SignatureType, native_enum=False), nullable=False)
    file_id = Column(String(36), nullable=True)
    signature_hash_sha256 = Column(String(64), nullable=False)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    certificate_id = Column(String(36), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)
    verification_details = Column(JSON, nullable=True)


@dataclass
class _AllowedDecision:
    allowed: bool = True
    reason: str | None = None


class _AllowAllPolicyEngine:
    def check(self, **kwargs):
        return _AllowedDecision()


class _RecordingDocumentClient:
    def __init__(self, *, sign_result: DocumentSignResult | None = None, verify_result: DocumentVerifyResult | None = None):
        self.sign_result = sign_result
        self.verify_result = verify_result
        self.last_sign_request = None
        self.last_verify_request = None

    def sign(self, request):
        self.last_sign_request = request
        if isinstance(self.sign_result, Exception):
            raise self.sign_result
        return self.sign_result

    def verify(self, request):
        self.last_verify_request = request
        if isinstance(self.verify_result, Exception):
            raise self.verify_result
        return self.verify_result


def _dedupe_table_indexes(*tables) -> None:
    for table in tables:
        seen: set[tuple[str | None, tuple[str, ...]]] = set()
        for index in list(table.indexes):
            signature = (index.name, tuple(column.name for column in index.columns))
            if signature in seen:
                table.indexes.remove(index)
            else:
                seen.add(signature)


def _create_minimal_signing_schema(engine) -> None:
    _dedupe_table_indexes(DocumentFile.__table__)
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Document.__table__,
            DocumentFile.__table__,
            AuditLog.__table__,
        ],
    )
    SigningBase.metadata.create_all(bind=engine)


@pytest.fixture
def isolated_signing_db(monkeypatch):
    import app.services.document_signing as signing_module

    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    original_signature_model = signing_module.DocumentSignature
    signing_module.DocumentSignature = SigningSignatureRecord

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_minimal_signing_schema(engine)
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
        signing_module.DocumentSignature = original_signature_model
        engine.dispose()



def _seed_document(session: Session) -> Document:
    item = Document(
        id="00000000-0000-0000-0000-000000000301",
        tenant_id=1,
        client_id="client-1",
        direction="INBOUND",
        title="Invoice",
        document_type=DocumentType.INVOICE,
        period_from=date(2025, 1, 1),
        period_to=date(2025, 1, 31),
        status=DocumentStatus.ISSUED,
        sender_type="NEFT",
        version=1,
    )
    session.add(item)
    session.flush()
    session.add(
        DocumentFile(
            id="00000000-0000-0000-0000-000000000302",
            document_id="00000000-0000-0000-0000-000000000301",
            file_type=DocumentFileType.PDF,
            bucket="docs",
            object_key="documents/client-1/2025-01-01_2025-01-31/v1.pdf",
            sha256="doc-hash",
            size_bytes=100,
            content_type="application/pdf",
        )
    )
    session.commit()
    return session.query(Document).filter(Document.id == "00000000-0000-0000-0000-000000000301").one()



def _build_signing_service(session: Session, *, document_client: _RecordingDocumentClient) -> DocumentSigningService:
    return DocumentSigningService(
        session,
        document_client=document_client,
        policy_engine=_AllowAllPolicyEngine(),
    )



def test_request_sign_success_uses_document_service_contract(isolated_signing_db):
    session_factory = isolated_signing_db
    session = session_factory()
    try:
        document = _seed_document(session)
        document_client = _RecordingDocumentClient(
            sign_result=DocumentSignResult(
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
        )
        service = _build_signing_service(session, document_client=document_client)

        result = service.request_sign(
            document_id=document.id,
            provider="provider_x",
            meta={"reason": "closing"},
            idempotency_key="idem-1",
            token=ADMIN_TOKEN,
        )

        session.expire_all()
        signature = session.query(SigningSignatureRecord).one()

        assert document_client.last_sign_request is not None
        assert document_client.last_sign_request.document_id == str(document.id)
        assert document_client.last_sign_request.provider == "provider_x"
        assert document_client.last_sign_request.input.bucket == "docs"
        assert document_client.last_sign_request.input.object_key.endswith("v1.pdf")
        assert document_client.last_sign_request.input.sha256 == "doc-hash"
        assert document_client.last_sign_request.output_bucket == "docs"
        assert document_client.last_sign_request.idempotency_key == "idem-1"
        assert document_client.last_sign_request.meta == {"reason": "closing"}

        assert result.signature.id == signature.id
        assert signature.status == DocumentSignatureStatus.SIGNED
        assert signature.request_id == "req-1"
        assert signature.signed_object_key.endswith("v1.signed.pdf")
        assert signature.signature_sha256 == "sig-hash"
        assert signature.signature_hash_sha256 == "sig-hash"
    finally:
        session.close()



def test_request_sign_failure_persists_failed_signature_state(isolated_signing_db):
    session_factory = isolated_signing_db
    session = session_factory()
    try:
        document = _seed_document(session)
        document_client = _RecordingDocumentClient(sign_result=RuntimeError("provider_down"))
        service = _build_signing_service(session, document_client=document_client)

        with pytest.raises(RuntimeError, match="provider_down"):
            service.request_sign(
                document_id=document.id,
                provider="provider_x",
                meta=None,
                idempotency_key=None,
                token=ADMIN_TOKEN,
            )

        session.expire_all()
        signature = session.query(SigningSignatureRecord).one()
        assert document_client.last_sign_request is not None
        assert signature.status == DocumentSignatureStatus.FAILED
        assert signature.error_code == "RuntimeError"
        assert signature.error_message == "provider_down"
    finally:
        session.close()



def test_verify_signature_uses_document_service_verify_contract(isolated_signing_db):
    session_factory = isolated_signing_db
    session = session_factory()
    try:
        document = _seed_document(session)
        signature = SigningSignatureRecord(
            document_id=document.id,
            provider="provider_x",
            version=1,
            status=DocumentSignatureStatus.SIGNED,
            input_object_key="documents/client-1/2025-01-01_2025-01-31/v1.pdf",
            input_sha256="doc-hash",
            signed_object_key="documents/client-1/2025-01-01_2025-01-31/v1.signed.pdf",
            signed_sha256="signed-hash",
            signature_object_key="documents/client-1/2025-01-01_2025-01-31/v1.sig.p7s",
            signature_sha256="sig-hash",
            attempt=1,
            meta={
                "input_bucket": "docs",
                "signed_bucket": "docs",
                "signature_bucket": "docs",
            },
            signature_type=SignatureType.ESIGN,
            signature_hash_sha256="sig-hash",
        )
        session.add(signature)
        session.commit()

        document_client = _RecordingDocumentClient(
            verify_result=DocumentVerifyResult(status="VERIFIED", verified=True, error_code=None)
        )
        service = _build_signing_service(session, document_client=document_client)

        result = service.verify_signature(
            document_id=document.id,
            signature_id=signature.id,
            token=ADMIN_TOKEN,
        )

        session.expire_all()
        refreshed_signature = session.query(SigningSignatureRecord).one()

        assert document_client.last_verify_request is not None
        assert document_client.last_verify_request.provider == "provider_x"
        assert document_client.last_verify_request.input.bucket == "docs"
        assert document_client.last_verify_request.input.object_key.endswith("v1.pdf")
        assert document_client.last_verify_request.signature.bucket == "docs"
        assert document_client.last_verify_request.signature.object_key.endswith("v1.sig.p7s")
        assert document_client.last_verify_request.signed is not None
        assert document_client.last_verify_request.signed.object_key.endswith("v1.signed.pdf")
        assert document_client.last_verify_request.meta["signature_bucket"] == "docs"

        assert result.verified is True
        assert result.status == "VERIFIED"
        assert refreshed_signature.status == DocumentSignatureStatus.VERIFIED
    finally:
        session.close()
