from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects import postgresql

from app.db import Base
from app.db.types import ExistingEnum, GUID


class EdoProvider(str, Enum):
    SBIS = "SBIS"


class EdoSubjectType(str, Enum):
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"
    INTERNAL = "INTERNAL"


class EdoDocumentStatus(str, Enum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    SIGNED = "SIGNED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class EdoDocumentKind(str, Enum):
    CONTRACT = "CONTRACT"
    INVOICE = "INVOICE"
    ACT = "ACT"
    RECON = "RECON"
    CLOSING = "CLOSING"
    OTHER = "OTHER"


class EdoCounterpartySubjectType(str, Enum):
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"


class EdoInboundStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class EdoArtifactType(str, Enum):
    SIGNED_PACKAGE = "SIGNED_PACKAGE"
    SIGNATURE = "SIGNATURE"
    RECEIPT = "RECEIPT"
    PROTOCOL = "PROTOCOL"
    OTHER = "OTHER"


class EdoTransitionActorType(str, Enum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    PROVIDER = "PROVIDER"


class EdoOutboxStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    DEAD = "DEAD"


JSONB_TYPE = postgresql.JSONB(none_as_null=True)
JSON_TYPE = JSON().with_variant(JSONB_TYPE, "postgresql")


class EdoAccount(Base):
    __tablename__ = "edo_accounts"

    id = Column(GUID(), primary_key=True)
    provider = Column(ExistingEnum(EdoProvider, name="edo_provider_v2"), nullable=False)
    name = Column(String(128), nullable=False)
    org_inn = Column(String(32), nullable=True)
    box_id = Column(String(128), nullable=False)
    credentials_ref = Column(String(256), nullable=False)
    webhook_secret_ref = Column(String(256), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EdoCounterparty(Base):
    __tablename__ = "edo_counterparties"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "subject_type",
            "subject_id",
            name="uq_edo_counterparty_mapping",
        ),
    )

    id = Column(GUID(), primary_key=True)
    subject_type = Column(ExistingEnum(EdoCounterpartySubjectType, name="edo_counterparty_subject_type"), nullable=False)
    subject_id = Column(String(64), nullable=False)
    provider = Column(ExistingEnum(EdoProvider, name="edo_provider_v2"), nullable=False)
    provider_counterparty_id = Column(String(128), nullable=False)
    provider_box_id = Column(String(128), nullable=True)
    display_name = Column(String(256), nullable=True)
    meta = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EdoDocument(Base):
    __tablename__ = "edo_documents"
    __table_args__ = (
        UniqueConstraint("send_dedupe_key", name="uq_edo_documents_send_dedupe_key"),
        Index("ix_edo_documents_status", "status"),
        Index("ix_edo_documents_subject", "subject_type", "subject_id"),
    )

    id = Column(GUID(), primary_key=True)
    provider = Column(ExistingEnum(EdoProvider, name="edo_provider_v2"), nullable=False)
    account_id = Column(GUID(), ForeignKey("edo_accounts.id"), nullable=False)
    subject_type = Column(ExistingEnum(EdoSubjectType, name="edo_subject_type"), nullable=False)
    subject_id = Column(String(64), nullable=False)
    document_registry_id = Column(GUID(), nullable=False)
    document_kind = Column(ExistingEnum(EdoDocumentKind, name="edo_document_kind"), nullable=False)
    provider_doc_id = Column(String(128), nullable=True)
    provider_thread_id = Column(String(128), nullable=True)
    status = Column(ExistingEnum(EdoDocumentStatus, name="edo_document_status_v2"), nullable=False)
    counterparty_id = Column(GUID(), ForeignKey("edo_counterparties.id"), nullable=False)
    send_dedupe_key = Column(String(256), nullable=False)
    attempts_send = Column(Integer, nullable=False, server_default="0")
    attempts_status = Column(Integer, nullable=False, server_default="0")
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    last_status_payload = Column(JSON_TYPE, nullable=True)
    requires_manual_intervention = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EdoTransition(Base):
    __tablename__ = "edo_transitions"
    __table_args__ = (Index("ix_edo_transitions_doc", "edo_document_id", "created_at"),)

    id = Column(GUID(), primary_key=True)
    edo_document_id = Column(GUID(), ForeignKey("edo_documents.id"), nullable=False)
    from_status = Column(ExistingEnum(EdoDocumentStatus, name="edo_document_status_v2"), nullable=True)
    to_status = Column(ExistingEnum(EdoDocumentStatus, name="edo_document_status_v2"), nullable=False)
    reason_code = Column(String(128), nullable=True)
    payload = Column(JSON_TYPE, nullable=True)
    actor_type = Column(ExistingEnum(EdoTransitionActorType, name="edo_transition_actor_type"), nullable=False)
    actor_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EdoInboundEvent(Base):
    __tablename__ = "edo_inbound_events"
    __table_args__ = (UniqueConstraint("provider_event_id", name="uq_edo_inbound_event_provider_id"),)

    id = Column(GUID(), primary_key=True)
    provider = Column(ExistingEnum(EdoProvider, name="edo_provider_v2"), nullable=False)
    provider_event_id = Column(String(128), nullable=False)
    headers = Column(JSON_TYPE, nullable=True)
    payload = Column(JSON_TYPE, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(ExistingEnum(EdoInboundStatus, name="edo_inbound_status"), nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EdoArtifact(Base):
    __tablename__ = "edo_artifacts"
    __table_args__ = (Index("ix_edo_artifacts_doc", "edo_document_id"),)

    id = Column(GUID(), primary_key=True)
    edo_document_id = Column(GUID(), ForeignKey("edo_documents.id"), nullable=False)
    artifact_type = Column(ExistingEnum(EdoArtifactType, name="edo_artifact_type"), nullable=False)
    document_registry_id = Column(GUID(), nullable=False)
    content_hash = Column(String(64), nullable=True)
    provider_ref = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EdoOutbox(Base):
    __tablename__ = "edo_outbox"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_edo_outbox_dedupe_key"),)

    id = Column(GUID(), primary_key=True)
    event_type = Column(String(64), nullable=False)
    payload = Column(JSON_TYPE, nullable=False)
    dedupe_key = Column(String(256), nullable=False)
    status = Column(ExistingEnum(EdoOutboxStatus, name="edo_outbox_status"), nullable=False)
    attempts = Column(Integer, nullable=False, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


__all__ = [
    "EdoAccount",
    "EdoArtifact",
    "EdoArtifactType",
    "EdoCounterparty",
    "EdoCounterpartySubjectType",
    "EdoDocument",
    "EdoDocumentKind",
    "EdoDocumentStatus",
    "EdoInboundEvent",
    "EdoInboundStatus",
    "EdoOutbox",
    "EdoOutboxStatus",
    "EdoProvider",
    "EdoSubjectType",
    "EdoTransition",
    "EdoTransitionActorType",
]
