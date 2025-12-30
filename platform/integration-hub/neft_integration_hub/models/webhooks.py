from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped

from neft_integration_hub.db import Base


class WebhookOwnerType(str, Enum):
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"


class WebhookEndpointStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class WebhookSigningAlgo(str, Enum):
    HMAC_SHA256 = "HMAC_SHA256"
    RSA = "RSA"


class WebhookDeliveryStatus(str, Enum):
    PENDING = "PENDING"
    PAUSED = "PAUSED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    DEAD = "DEAD"


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_type: Mapped[str] = Column(String(16), nullable=False, index=True)
    owner_id: Mapped[str] = Column(String(64), nullable=False, index=True)
    url: Mapped[str] = Column(Text, nullable=False)
    status: Mapped[str] = Column(String(16), nullable=False, default=WebhookEndpointStatus.ACTIVE.value)
    signing_algo: Mapped[str] = Column(String(32), nullable=False, default=WebhookSigningAlgo.HMAC_SHA256.value)
    secret_encrypted: Mapped[str] = Column(Text, nullable=False)
    delivery_paused: Mapped[bool] = Column(Boolean, nullable=False, default=False)
    paused_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    paused_reason: Mapped[str | None] = Column(Text, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"
    __table_args__ = (
        UniqueConstraint("endpoint_id", "event_type", "schema_version", name="uq_webhook_subscription"),
    )

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    endpoint_id: Mapped[str] = Column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = Column(String(128), nullable=False, index=True)
    schema_version: Mapped[int] = Column(Integer, nullable=False, default=1)
    filters: Mapped[dict | None] = Column(JSON, nullable=True)
    enabled: Mapped[bool] = Column(Boolean, nullable=False, default=True)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("endpoint_id", "event_id", "replay_id", name="uq_webhook_delivery_event"),
        Index("ix_webhook_deliveries_status_retry", "status", "next_retry_at"),
    )

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    endpoint_id: Mapped[str] = Column(String(36), nullable=False, index=True)
    event_id: Mapped[str] = Column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = Column(String(128), nullable=False, index=True)
    payload: Mapped[dict | None] = Column(JSON, nullable=True)
    attempt: Mapped[int] = Column(Integer, nullable=False, default=0)
    status: Mapped[str] = Column(String(16), nullable=False, default=WebhookDeliveryStatus.PENDING.value)
    last_http_status: Mapped[int | None] = Column(Integer, nullable=True)
    last_error: Mapped[str | None] = Column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    replay_id: Mapped[str | None] = Column(String(36), nullable=True, index=True)
    occurred_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = Column(Integer, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WebhookReplay(Base):
    __tablename__ = "webhook_replays"

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    endpoint_id: Mapped[str] = Column(String(36), nullable=False, index=True)
    from_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    to_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    event_types: Mapped[list[str] | None] = Column(JSON, nullable=True)
    scheduled_count: Mapped[int] = Column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[str | None] = Column(String(64), nullable=True)


class WebhookAlertType(str, Enum):
    DELIVERY_FAILURE = "DELIVERY_FAILURE"
    SLA_BREACH = "SLA_BREACH"
    PAUSED_TOO_LONG = "PAUSED_TOO_LONG"


class WebhookAlert(Base):
    __tablename__ = "webhook_alerts"

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    endpoint_id: Mapped[str] = Column(String(36), nullable=False, index=True)
    partner_id: Mapped[str] = Column(String(64), nullable=False, index=True)
    type: Mapped[str] = Column(String(32), nullable=False)
    window: Mapped[str] = Column(String(16), nullable=False)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)


__all__ = [
    "WebhookAlert",
    "WebhookAlertType",
    "WebhookDelivery",
    "WebhookDeliveryStatus",
    "WebhookEndpoint",
    "WebhookEndpointStatus",
    "WebhookOwnerType",
    "WebhookReplay",
    "WebhookSigningAlgo",
    "WebhookSubscription",
]
