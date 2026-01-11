from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, String, Text, event, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class LegalDocumentStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class LegalDocumentContentType(str, Enum):
    MARKDOWN = "MARKDOWN"
    HTML = "HTML"
    PLAIN = "PLAIN"


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    code = Column(String(64), nullable=False)
    version = Column(String(32), nullable=False)
    title = Column(String(256), nullable=False)
    locale = Column(String(8), nullable=False, default="ru")
    effective_from = Column(DateTime(timezone=True), nullable=False)
    status = Column(ExistingEnum(LegalDocumentStatus, name="legal_document_status"), nullable=False)
    content_type = Column(
        ExistingEnum(LegalDocumentContentType, name="legal_document_content_type"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_by = Column(String(128), nullable=True)

__all__ = ["LegalDocument", "LegalDocumentContentType", "LegalDocumentStatus"]
