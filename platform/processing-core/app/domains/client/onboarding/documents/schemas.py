from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.client.onboarding.documents.models import DocStatus, DocType


class DocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    doc_type: DocType
    filename: str
    status: DocStatus
    size: int
    mime: str
    rejection_reason: str | None = None
    created_at: datetime


class UploadDocumentResponse(DocumentItem):
    pass


class ListDocumentsResponse(BaseModel):
    items: list[DocumentItem]
