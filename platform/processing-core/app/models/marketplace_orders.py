from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, Text, event, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class MarketplaceOrderStatus(str, Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MarketplaceOrderEventType(str, Enum):
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_STARTED = "ORDER_STARTED"
    ORDER_PROGRESS_UPDATED = "ORDER_PROGRESS_UPDATED"
    ORDER_COMPLETED = "ORDER_COMPLETED"
    ORDER_FAILED = "ORDER_FAILED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_NOTE_ADDED = "ORDER_NOTE_ADDED"


class MarketplaceOrderActorType(str, Enum):
    CLIENT = "client"
    PARTNER = "partner"
    ADMIN = "admin"
    SYSTEM = "system"


class MarketplaceOrderImmutableError(ValueError):
    """Raised when WORM-protected marketplace order records are mutated."""


class MarketplaceOrder(Base):
    __tablename__ = "marketplace_orders"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    product_id = Column(GUID(), nullable=False, index=True)
    quantity = Column(Numeric(18, 4), nullable=False)
    price_snapshot = Column(JSON_TYPE, nullable=False)
    price = Column(Numeric(18, 4), nullable=True)
    discount = Column(Numeric(18, 4), nullable=True)
    final_price = Column(Numeric(18, 4), nullable=True)
    commission = Column(Numeric(18, 4), nullable=True)
    status = Column(
        ExistingEnum(MarketplaceOrderStatus, name="marketplace_order_status"),
        nullable=False,
        default=MarketplaceOrderStatus.CREATED.value,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    audit_event_id = Column(GUID(), nullable=True)
    external_ref = Column(Text, nullable=True)


class MarketplaceOrderEvent(Base):
    __tablename__ = "marketplace_order_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(GUID(), ForeignKey("marketplace_orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    event_type = Column(
        ExistingEnum(MarketplaceOrderEventType, name="marketplace_order_event_type"), nullable=False
    )
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    payload_redacted = Column(JSON_TYPE, nullable=False)
    actor_type = Column(
        ExistingEnum(MarketplaceOrderActorType, name="marketplace_order_actor_type"),
        nullable=False,
    )
    actor_id = Column(GUID(), nullable=True)
    audit_event_id = Column(GUID(), ForeignKey("case_events.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


@event.listens_for(MarketplaceOrderEvent, "before_update")
@event.listens_for(MarketplaceOrderEvent, "before_delete")
def _block_marketplace_order_event_mutation(mapper, connection, target: MarketplaceOrderEvent) -> None:
    raise MarketplaceOrderImmutableError("marketplace_order_event_immutable")


__all__ = [
    "MarketplaceOrder",
    "MarketplaceOrderActorType",
    "MarketplaceOrderEvent",
    "MarketplaceOrderEventType",
    "MarketplaceOrderImmutableError",
    "MarketplaceOrderStatus",
]
