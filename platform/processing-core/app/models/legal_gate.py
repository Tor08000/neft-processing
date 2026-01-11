from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db import Base
from app.db.types import ExistingEnum, GUID


class LegalDocumentStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"


class LegalSubjectType(str, Enum):
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"
    USER = "USER"


class LegalDocument(Base):
    __tablename__ = "legal_documents"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_legal_documents_code_version"),)

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    code = Column(String(64), nullable=False, index=True)
    title = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(
        ExistingEnum(LegalDocumentStatus, name="legal_document_status"),
        nullable=False,
        default=LegalDocumentStatus.DRAFT,
        index=True,
    )
    effective_from = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    acceptances = relationship("LegalAcceptance", back_populates="document")


class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"
    __table_args__ = (
        UniqueConstraint("subject_type", "subject_id", "document_id", name="uq_legal_acceptances_scope"),
    )

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(GUID(), ForeignKey("legal_documents.id"), nullable=False, index=True)
    subject_type = Column(ExistingEnum(LegalSubjectType, name="legal_subject_type"), nullable=False, index=True)
    subject_id = Column(Text, nullable=False, index=True)
    accepted_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("LegalDocument", back_populates="acceptances")


__all__ = ["LegalDocument", "LegalAcceptance", "LegalDocumentStatus", "LegalSubjectType"]
