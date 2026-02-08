from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class MarketplaceClientEventType(str, Enum):
    OFFER_VIEWED = "marketplace.offer_viewed"
    OFFER_CLICKED = "marketplace.offer_clicked"
    SEARCH_PERFORMED = "marketplace.search_performed"
    ORDER_CREATED = "marketplace.order_created"
    ORDER_PAID = "marketplace.order_paid"
    ORDER_CANCELED = "marketplace.order_canceled"
    PRODUCT_VIEWED = "marketplace.product_viewed"
    SERVICE_VIEWED = "marketplace.service_viewed"
    FILTERS_CHANGED = "marketplace.filters_changed"
    CHECKOUT_STARTED = "marketplace.checkout_started"


class MarketplaceClientEntityType(str, Enum):
    OFFER = "OFFER"
    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"
    ORDER = "ORDER"
    NONE = "NONE"


class MarketplaceClientEventSource(str, Enum):
    CLIENT_PORTAL = "client_portal"
    WEB = "web"
    MOBILE = "mobile"
    API = "api"


class MarketplaceClientEvent(Base):
    __tablename__ = "marketplace_client_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    ts = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    client_ts = Column(DateTime(timezone=True), nullable=True)
    client_id = Column(GUID(), nullable=False, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_id = Column(GUID(), nullable=True)
    session_id = Column(String(128), nullable=True)
    event_type = Column(
        ExistingEnum(MarketplaceClientEventType, name="marketplace_client_event_type"),
        nullable=False,
    )
    entity_type = Column(
        ExistingEnum(MarketplaceClientEntityType, name="marketplace_client_entity_type"),
        nullable=False,
        default=MarketplaceClientEntityType.NONE,
    )
    entity_id = Column(GUID(), nullable=True)
    source = Column(
        ExistingEnum(MarketplaceClientEventSource, name="marketplace_client_event_source"),
        nullable=False,
    )
    page = Column(Text(), nullable=True)
    utm = Column(JSON_TYPE, nullable=True)
    payload = Column(JSON_TYPE, nullable=True)
    request_id = Column(String(128), nullable=True)
    idempotency_key = Column(String(128), nullable=True)


__all__ = [
    "MarketplaceClientEntityType",
    "MarketplaceClientEvent",
    "MarketplaceClientEventSource",
    "MarketplaceClientEventType",
]
