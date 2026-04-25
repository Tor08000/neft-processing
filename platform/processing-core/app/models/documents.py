from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db import Base
from app.db.types import ExistingEnum, GUID


class DocumentType(str, Enum):
    INVOICE = "INVOICE"
    SUBSCRIPTION_INVOICE = "SUBSCRIPTION_INVOICE"
    SUBSCRIPTION_ACT = "SUBSCRIPTION_ACT"
    ACT = "ACT"
    RECONCILIATION_ACT = "RECONCILIATION_ACT"
    CLOSING_PACKAGE = "CLOSING_PACKAGE"
    OFFER = "OFFER"


class DocumentStatus(str, Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FINALIZED = "FINALIZED"
    VOID = "VOID"


class DocumentFileType(str, Enum):
    PDF = "PDF"
    XLSX = "XLSX"
    SIG = "SIG"
    P7S = "P7S"
    CERT = "CERT"
    EDI_XML = "EDI_XML"


class DocumentDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class EdoProvider(str, Enum):
    DIADOK = "DIADOK"
    SBIS = "SBIS"


class EdoDocumentStatus(str, Enum):
    QUEUED = "QUEUED"
    UPLOADING = "UPLOADING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    SIGNED_BY_US = "SIGNED_BY_US"
    SIGNED_BY_COUNTERPARTY = "SIGNED_BY_COUNTERPARTY"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ClosingPackageStatus(str, Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FINALIZED = "FINALIZED"
    VOID = "VOID"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("period_from <= period_to", name="ck_documents_period"),
        UniqueConstraint(
            "tenant_id",
            "client_id",
            "document_type",
            "period_from",
            "period_to",
            "version",
            name="uq_documents_scope",
        ),
        {"extend_existing": True},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    direction = Column(
        ExistingEnum(DocumentDirection, name="documents_direction"),
        nullable=False,
        server_default=DocumentDirection.INBOUND.value,
    )
    title = Column(Text, nullable=False, server_default="")
    category = Column(Text, nullable=True)
    doc_type = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    document_type = Column(ExistingEnum(DocumentType, name="document_type"), nullable=False, index=True)
    period_from = Column(Date, nullable=False, index=True)
    period_to = Column(Date, nullable=False, index=True)
    status = Column(
        ExistingEnum(DocumentStatus, name="document_status"),
        nullable=False,
        index=True,
        default=DocumentStatus.DRAFT,
    )
    sender_type = Column(String(32), nullable=False, server_default="NEFT")
    sender_name = Column(Text, nullable=True)
    counterparty_name = Column(Text, nullable=True)
    counterparty_inn = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    number = Column(Text, nullable=True)
    date = Column(Date, nullable=True)
    amount = Column(Numeric(18, 2), nullable=True)
    currency = Column(Text, nullable=True)
    source_entity_type = Column(Text, nullable=True)
    source_entity_id = Column(Text, nullable=True)
    document_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    ack_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    signed_by_client_at = Column(DateTime(timezone=True), nullable=True)
    signed_by_client_user_id = Column(GUID(), nullable=True)
    created_by_actor_type = Column(String(32), nullable=True)
    created_by_actor_id = Column(Text, nullable=True)
    created_by_email = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)

    files = relationship("app.models.documents.DocumentFile", back_populates="document", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        kwargs.setdefault("id", str(uuid4()))
        super().__init__(**kwargs)


class DocumentFile(Base):
    __tablename__ = "document_files"
    __table_args__ = (
        UniqueConstraint("document_id", "file_type", name="uq_document_files_type"),
        {"extend_existing": True},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    file_type = Column(ExistingEnum(DocumentFileType, name="document_file_type"), nullable=False)
    bucket = Column(Text, nullable=False)
    object_key = Column(Text, nullable=False)
    storage_key = Column(Text, nullable=False)
    filename = Column(Text, nullable=False)
    mime = Column(Text, nullable=False)
    sha256 = Column(String(64), nullable=False)
    size = Column(BigInteger, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    content_type = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)

    document = relationship("app.models.documents.Document", back_populates="files")

    def __init__(self, **kwargs):
        kwargs.setdefault("id", str(uuid4()))
        object_key = kwargs.get("object_key")
        storage_key = kwargs.get("storage_key")
        if storage_key is None and object_key is not None:
            kwargs["storage_key"] = object_key
        elif object_key is None and storage_key is not None:
            kwargs["object_key"] = storage_key

        content_type = kwargs.get("content_type")
        mime = kwargs.get("mime")
        if mime is None and content_type is not None:
            kwargs["mime"] = content_type
        elif content_type is None and mime is not None:
            kwargs["content_type"] = mime

        size_bytes = kwargs.get("size_bytes")
        size = kwargs.get("size")
        if size is None and size_bytes is not None:
            kwargs["size"] = size_bytes
        elif size_bytes is None and size is not None:
            kwargs["size_bytes"] = size

        filename = kwargs.get("filename")
        resolved_storage_key = kwargs.get("storage_key") or kwargs.get("object_key")
        if filename is None and resolved_storage_key:
            kwargs["filename"] = str(resolved_storage_key).rsplit("/", 1)[-1]

        super().__init__(**kwargs)


def _repair_mapper_against_current_table(mapper_cls) -> None:
    mapper = mapper_cls.__mapper__
    for prop in mapper.column_attrs:
        for column in prop.columns:
            current_column = mapper_cls.__table__.c.get(column.key)
            if current_column is not None and current_column not in mapper._columntoproperty:
                mapper._columntoproperty[current_column] = prop


def repair_document_table_mappers() -> None:
    _repair_mapper_against_current_table(Document)
    _repair_mapper_against_current_table(DocumentFile)


class ClosingPackage(Base):
    __tablename__ = "closing_packages"
    __table_args__ = (
        CheckConstraint("period_from <= period_to", name="ck_closing_packages_period"),
        UniqueConstraint(
            "tenant_id",
            "client_id",
            "period_from",
            "period_to",
            "version",
            name="uq_closing_packages_scope",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    period_from = Column(Date, nullable=False, index=True)
    period_to = Column(Date, nullable=False, index=True)
    status = Column(
        ExistingEnum(ClosingPackageStatus, name="closing_package_status"),
        nullable=False,
        index=True,
        default=ClosingPackageStatus.DRAFT,
    )
    version = Column(Integer, nullable=False, default=1)
    invoice_document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    act_document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    recon_document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    ack_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON, nullable=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("id", str(uuid4()))
        super().__init__(**kwargs)


class DocumentEdoStatus(Base):
    __tablename__ = "document_edo_status"
    __table_args__ = (
        UniqueConstraint("document_id", "provider", name="uq_document_edo_status_document_provider"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    signature_id = Column(String(36), nullable=True)
    provider = Column(ExistingEnum(EdoProvider, name="edo_provider"), nullable=False, index=True)
    status = Column(ExistingEnum(EdoDocumentStatus, name="edo_document_status"), nullable=False, index=True)

    provider_message_id = Column(String(128), nullable=True)
    provider_document_id = Column(String(128), nullable=True)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_status_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON, nullable=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("id", str(uuid4()))
        super().__init__(**kwargs)
