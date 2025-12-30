from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EdoEventPayload(BaseModel):
    document_id: UUID
    signature_id: UUID | None = None
    provider: str
    status: str
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class EdoEventEnvelope(BaseModel):
    event_id: UUID
    occurred_at: datetime
    correlation_id: str
    trace_id: str
    schema_version: str
    event_type: str
    payload: EdoEventPayload


__all__ = ["EdoEventEnvelope", "EdoEventPayload"]
