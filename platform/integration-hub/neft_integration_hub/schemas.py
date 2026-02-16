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


class EdoStubSendRequest(BaseModel):
    doc_id: str
    counterparty: dict
    payload_ref: str
    meta: dict | None = None


class EdoStubSendResponse(BaseModel):
    edo_doc_id: str
    status: str


class EdoStubStatusResponse(BaseModel):
    edo_doc_id: str
    status: str


class EdoStubSimulateRequest(BaseModel):
    status: str
    note: str | None = None




class EdoIntDocumentFile(BaseModel):
    storage_key: str
    filename: str
    sha256: str | None = None
    mime: str
    size: int


class EdoIntDocument(BaseModel):
    document_id: str
    client_id: str
    title: str
    category: str | None = None
    files: list[EdoIntDocumentFile]
    meta: dict = Field(default_factory=dict)


class EdoIntSendRequest(BaseModel):
    idempotency_key: str
    provider: str
    document: EdoIntDocument


class EdoIntSendResponse(BaseModel):
    edo_message_id: str
    edo_status: str
    provider: str
    provider_mode: str


class EdoIntStatusResponse(BaseModel):
    edo_message_id: str
    edo_status: str
    provider_status_raw: dict = Field(default_factory=dict)
    updated_at: datetime

class NotificationSendRequest(BaseModel):
    channel: str
    template: str
    to: str
    variables: dict = Field(default_factory=dict)


class NotificationSendResponse(BaseModel):
    status: str
    mode: str




class NotifyEmailSendRequest(BaseModel):
    to: str
    subject: str
    html: str | None = None
    text: str | None = None
    meta: dict = Field(default_factory=dict)


class NotifyEmailSendResponse(BaseModel):
    status: str
    message_id: str

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


class WebhookIntakeRequest(BaseModel):
    event_type: str
    payload: dict
    event_id: str | None = None
    occurred_at: str | None = None
    correlation_id: str | None = None


class WebhookIntakeResponse(BaseModel):
    event_id: str | None = None
    status: str
    verified: bool


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
    delivery_paused: bool = False
    paused_at: datetime | None = None
    paused_reason: str | None = None
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
    occurred_at: datetime | None = None
    latency_ms: int | None = None


class WebhookTestResponse(BaseModel):
    event_id: str
    delivery_id: str
    status: str


class WebhookTestDeliveryRequest(BaseModel):
    endpoint_id: str
    event_type: str | None = None
    payload: dict | None = None


class WebhookRotateSecretResponse(BaseModel):
    endpoint_id: str
    secret: str


class WebhookPauseRequest(BaseModel):
    reason: str | None = None


class WebhookReplayRequest(BaseModel):
    from_at: datetime = Field(alias="from")
    to_at: datetime = Field(alias="to")
    event_types: list[str] | None = None
    only_failed: bool = False

    class Config:
        allow_population_by_field_name = True


class WebhookReplayResponse(BaseModel):
    replay_id: str
    scheduled_deliveries: int


class WebhookSlaResponse(BaseModel):
    window: str
    success_ratio: float
    avg_latency_ms: int | None = None
    sla_breaches: int


class WebhookAlertResponse(BaseModel):
    id: str
    type: str
    window: str
    created_at: datetime



__all__ = [
    "ArtifactRef",
    "CounterpartyRef",
    "DispatchRequest",
    "DispatchResponse",
    "EdoDocumentResponse",
    "EdoIntDocument",
    "EdoIntDocumentFile",
    "EdoIntSendRequest",
    "EdoIntSendResponse",
    "EdoIntStatusResponse",
    "EdoStubSendRequest",
    "EdoStubSendResponse",
    "EdoStubSimulateRequest",
    "EdoStubStatusResponse",
    "NotificationSendRequest",
    "NotificationSendResponse",
    "NotifyEmailSendRequest",
    "NotifyEmailSendResponse",
    "WebhookDeliveryResponse",
    "WebhookEndpointCreate",
    "WebhookEndpointResponse",
    "WebhookEndpointSecretResponse",
    "WebhookEventEnvelope",
    "WebhookIntakeRequest",
    "WebhookIntakeResponse",
    "WebhookAlertResponse",
    "WebhookOwner",
    "WebhookPauseRequest",
    "WebhookReplayRequest",
    "WebhookReplayResponse",
    "WebhookRotateSecretResponse",
    "WebhookSlaResponse",
    "WebhookSubscriptionCreate",
    "WebhookSubscriptionResponse",
    "WebhookTestResponse",
    "WebhookTestDeliveryRequest",
]
