from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderError(BaseModel):
    provider_error_code: str
    provider_message: str
    request_id: str | None = None
    retryable: bool = False


class ProviderEnvelope(BaseModel):
    ok: bool = True
    request_id: str | None = None
    error: ProviderError | None = None


class IdempotentResponse(BaseModel):
    idempotency_key: str | None = None
    idempotency_status: str | None = Field(default=None, description="new|replayed|processing")
