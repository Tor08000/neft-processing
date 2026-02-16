from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GeneratedDocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_application_id: str | None
    client_id: str | None
    doc_kind: str
    version: int
    filename: str
    mime: str
    size: int | None
    status: str
    template_id: str | None
    created_at: datetime


class GeneratedDocumentsListResponse(BaseModel):
    items: list[GeneratedDocumentItem]
