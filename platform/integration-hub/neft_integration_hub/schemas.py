from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ArtifactRef(BaseModel):
    bucket: str
    object_key: str
    sha256: str | None = None


class CounterpartyRef(BaseModel):
    inn: str
    kpp: str
    edo_id: str | None = None


class DispatchRequest(BaseModel):
    document_id: str
    signature_id: str | None = None
    provider: str
    artifact: ArtifactRef
    counterparty: CounterpartyRef
    idempotency_key: str
    meta: dict = Field(default_factory=dict)


class DispatchResponse(BaseModel):
    status: str
    edo_document_id: str


class EdoDocumentResponse(BaseModel):
    edo_document_id: str
    document_id: str
    signature_id: str | None = None
    provider: str
    status: str
    provider_message_id: str | None = None
    provider_document_id: str | None = None
    attempt: int
    last_error: str | None = None


class WebhookOwner(BaseModel):
    type: str
    id: str


class WebhookEventEnvelope(BaseModel):
    event_id: str
    event_type: str
    occurred_at: str
    schema_version: int
    correlation_id: str
    owner: WebhookOwner
    payload: dict


class WebhookEndpointCreate(BaseModel):
    owner_type: str
    owner_id: str
    url: str
    signing_algo: str = "HMAC_SHA256"


class WebhookEndpointResponse(BaseModel):
    id: str
    owner_type: str
    owner_id: str
    url: str
    status: str
    signing_algo: str
    created_at: datetime
    updated_at: datetime


class WebhookEndpointSecretResponse(WebhookEndpointResponse):
    secret: str


class WebhookSubscriptionCreate(BaseModel):
    endpoint_id: str
    event_type: str
    schema_version: int = 1
    filters: dict | None = None
    enabled: bool = True


class WebhookSubscriptionResponse(BaseModel):
    id: str
    endpoint_id: str
    event_type: str
    schema_version: int
    filters: dict | None = None
    enabled: bool


class WebhookDeliveryResponse(BaseModel):
    id: str
    endpoint_id: str
    event_id: str
    event_type: str
    attempt: int
    status: str
    last_http_status: int | None = None
    last_error: str | None = None
    next_retry_at: datetime | None = None


class WebhookTestResponse(BaseModel):
    event_id: str
    delivery_id: str
    status: str


class WebhookRotateSecretResponse(BaseModel):
    endpoint_id: str
    secret: str


__all__ = [
    "ArtifactRef",
    "CounterpartyRef",
    "DispatchRequest",
    "DispatchResponse",
    "EdoDocumentResponse",
    "WebhookDeliveryResponse",
    "WebhookEndpointCreate",
    "WebhookEndpointResponse",
    "WebhookEndpointSecretResponse",
    "WebhookEventEnvelope",
    "WebhookOwner",
    "WebhookRotateSecretResponse",
    "WebhookSubscriptionCreate",
    "WebhookSubscriptionResponse",
    "WebhookTestResponse",
]
