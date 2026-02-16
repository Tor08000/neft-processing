from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.client.generated_docs.schemas import GeneratedDocumentItem


class SignRequestPayload(BaseModel):
    phone: str | None = None
    channel: str | None = None
    consent: bool


class SignRequestResponse(BaseModel):
    request_id: str
    expires_at: datetime
    otp_code: str | None = None


class SignConfirmPayload(BaseModel):
    request_id: str
    otp_code: str


class CheckboxSignPayload(BaseModel):
    consent: bool


class SignedDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doc: GeneratedDocumentItem
