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
    client_signed_at: datetime | None = None
    client_sign_method: str | None = None
    client_sign_phone: str | None = None
    client_signature_hash: str | None = None


class GeneratedDocumentsListResponse(BaseModel):
    items: list[GeneratedDocumentItem]
