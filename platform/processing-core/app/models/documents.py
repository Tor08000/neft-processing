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
    )

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    document_type = Column(ExistingEnum(DocumentType, name="document_type"), nullable=False, index=True)
    period_from = Column(Date, nullable=False, index=True)
    period_to = Column(Date, nullable=False, index=True)
    status = Column(
        ExistingEnum(DocumentStatus, name="document_status"),
        nullable=False,
        index=True,
        default=DocumentStatus.DRAFT,
    )
    version = Column(Integer, nullable=False, default=1)
    number = Column(Text, nullable=True)
    source_entity_type = Column(Text, nullable=True)
    source_entity_id = Column(Text, nullable=True)
    document_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    ack_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_by_actor_type = Column(String(32), nullable=True)
    created_by_actor_id = Column(Text, nullable=True)
    created_by_email = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)

    files = relationship("DocumentFile", back_populates="document", cascade="all, delete-orphan")


class DocumentFile(Base):
    __tablename__ = "document_files"
    __table_args__ = (
        UniqueConstraint("document_id", "file_type", name="uq_document_files_type"),
    )

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=False, index=True)
    file_type = Column(ExistingEnum(DocumentFileType, name="document_file_type"), nullable=False)
    bucket = Column(Text, nullable=False)
    object_key = Column(Text, nullable=False)
    sha256 = Column(String(64), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    content_type = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)

    document = relationship("Document", back_populates="files")


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

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
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
    invoice_document_id = Column(GUID(), ForeignKey("documents.id"), nullable=True)
    act_document_id = Column(GUID(), ForeignKey("documents.id"), nullable=True)
    recon_document_id = Column(GUID(), ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    ack_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON, nullable=True)
