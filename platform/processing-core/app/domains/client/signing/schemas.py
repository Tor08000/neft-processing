from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.client.generated_docs.schemas import GeneratedDocumentItem


class SignRequestPayload(BaseModel):
    channel: str | None = None
    destination: str


class SignRequestResponse(BaseModel):
    challenge_id: str
    expires_at: datetime
    resend_available_at: datetime
    channel: str
    masked_destination: str
    otp_code: str | None = None


class SignConfirmPayload(BaseModel):
    challenge_id: str
    code: str


class CheckboxSignPayload(BaseModel):
    consent: bool


class SignedDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doc: GeneratedDocumentItem
    otp: dict | None = None
