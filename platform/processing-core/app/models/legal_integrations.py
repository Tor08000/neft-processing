from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID


class DocumentEnvelopeStatus(str, Enum):
    CREATED = "CREATED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    SIGNED = "SIGNED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class SignatureType(str, Enum):
    ESIGN = "ESIGN"
    KEP = "KEP"
    GOST_P7S = "GOST_P7S"
    EDI_SIGN = "EDI_SIGN"


class DocumentEnvelope(Base):
    __tablename__ = "document_envelopes"
    __table_args__ = (
        UniqueConstraint("provider", "envelope_id", name="uq_document_envelopes_provider"),
    )

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    envelope_id = Column(String(128), nullable=False)
    status = Column(ExistingEnum(DocumentEnvelopeStatus, name="document_envelope_status"), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    last_status_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)


class DocumentSignature(Base):
    __tablename__ = "document_signatures"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    signature_type = Column(ExistingEnum(SignatureType, name="signature_type"), nullable=False)
    file_id = Column(GUID(), ForeignKey("document_files.id"), nullable=True)
    signature_hash_sha256 = Column(String(64), nullable=False)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    certificate_id = Column(GUID(), ForeignKey("certificates.id"), nullable=True)
    verified = Column(Boolean, nullable=False, server_default="false")
    verification_details = Column(JSON, nullable=True)


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    subject_dn = Column(Text, nullable=True)
    issuer_dn = Column(Text, nullable=True)
    serial_number = Column(Text, nullable=True)
    thumbprint_sha256 = Column(String(64), nullable=True, index=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, nullable=False, server_default="false")
    revocation_checked_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON, nullable=True)


class LegalProviderConfig(Base):
    __tablename__ = "legal_provider_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_legal_provider_configs_scope"),
    )

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    signing_provider = Column(String(64), nullable=False, server_default="none")
    edo_provider = Column(String(64), nullable=False, server_default="none")
    require_signature_for_finalize = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


__all__ = [
    "Certificate",
    "DocumentEnvelope",
    "DocumentEnvelopeStatus",
    "DocumentSignature",
    "LegalProviderConfig",
    "SignatureType",
]
