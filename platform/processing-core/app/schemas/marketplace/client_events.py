from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


MarketplaceClientEventType = Literal[
    "marketplace.offer_viewed",
    "marketplace.offer_clicked",
    "marketplace.search_performed",
    "marketplace.order_created",
    "marketplace.order_paid",
    "marketplace.order_canceled",
    "marketplace.product_viewed",
    "marketplace.service_viewed",
    "marketplace.filters_changed",
    "marketplace.checkout_started",
]

MarketplaceClientEntityType = Literal["OFFER", "PRODUCT", "SERVICE", "ORDER", "NONE"]
MarketplaceClientEventSource = Literal["client_portal", "web", "mobile", "api"]

EVENT_TYPE_WHITELIST = set(MarketplaceClientEventType.__args__)
ENTITY_TYPE_WHITELIST = set(MarketplaceClientEntityType.__args__)
PAYLOAD_MAX_BYTES = 16 * 1024


class MarketplaceClientEventIn(BaseModel):
    event_type: str
    entity_type: MarketplaceClientEntityType = "NONE"
    entity_id: UUID | None = None
    session_id: str | None = None
    source: MarketplaceClientEventSource = "client_portal"
    page: str | None = None
    utm: dict | None = None
    payload: dict | None = None
    client_ts: datetime | None = None
    request_id: str | None = None
    idempotency_key: str | None = None

    @field_validator("payload")
    @classmethod
    def payload_is_object_and_size_limited(cls, value: dict | None) -> dict | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("payload must be a JSON object")
        payload_size = len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        if payload_size > PAYLOAD_MAX_BYTES:
            raise ValueError("payload exceeds size limit")
        return value

    @field_validator("utm")
    @classmethod
    def utm_is_object(cls, value: dict | None) -> dict | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("utm must be a JSON object")
        return value

    @model_validator(mode="after")
    def entity_id_required_for_entity_type(self) -> MarketplaceClientEventIn:
        if self.entity_type != "NONE" and self.entity_id is None:
            raise ValueError("entity_id is required for entity_type events")
        return self


class MarketplaceClientEventsIngestRequest(BaseModel):
    events: list[MarketplaceClientEventIn] = Field(default_factory=list)


class MarketplaceClientEventOut(BaseModel):
    id: str
    ts: datetime
    client_ts: datetime | None = None
    client_id: str
    tenant_id: int | None = None
    user_id: str | None = None
    session_id: str | None = None
    event_type: str
    entity_type: MarketplaceClientEntityType
    entity_id: str | None = None
    source: MarketplaceClientEventSource
    page: str | None = None
    utm: dict | None = None
    payload: dict | None = None
    request_id: str | None = None
    idempotency_key: str | None = None


class MarketplaceClientEventsIngestResponse(BaseModel):
    accepted: int
    rejected: int


class MarketplaceClientEventsQueryResponse(BaseModel):
    items: list[MarketplaceClientEventOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
