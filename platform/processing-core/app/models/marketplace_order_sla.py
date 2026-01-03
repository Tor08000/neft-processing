from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, event, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.models.marketplace_orders import MarketplaceOrderEvent


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class OrderSlaStatus(str, Enum):
    OK = "OK"
    VIOLATION = "VIOLATION"


class OrderSlaSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OrderSlaConsequenceType(str, Enum):
    PENALTY_FEE = "PENALTY_FEE"
    CREDIT_NOTE = "CREDIT_NOTE"
    REFUND = "REFUND"


class OrderSlaConsequenceStatus(str, Enum):
    APPLIED = "APPLIED"
    FAILED = "FAILED"


class MarketplaceSlaNotificationStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class MarketplaceOrderContractLink(Base):
    __tablename__ = "marketplace_order_contract_links"

    order_id = Column(String(64), primary_key=True)
    contract_id = Column(GUID(), ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False)
    sla_policy_version = Column(Integer, nullable=True)
    bound_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    audit_event_id = Column(GUID(), nullable=False)


class OrderSlaEvaluation(Base):
    __tablename__ = "order_sla_evaluations"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(String(64), nullable=False, index=True)
    contract_id = Column(GUID(), ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False)
    obligation_id = Column(GUID(), ForeignKey("contract_obligations.id", ondelete="RESTRICT"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    measured_value = Column(Numeric(18, 4), nullable=False)
    status = Column(ExistingEnum(OrderSlaStatus, name="order_sla_status"), nullable=False)
    breach_reason = Column(Text, nullable=True)
    breach_severity = Column(ExistingEnum(OrderSlaSeverity, name="order_sla_severity"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    audit_event_id = Column(GUID(), nullable=False)


class OrderSlaConsequence(Base):
    __tablename__ = "order_sla_consequences"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(String(64), nullable=False, index=True)
    evaluation_id = Column(GUID(), ForeignKey("order_sla_evaluations.id", ondelete="CASCADE"), nullable=False)
    consequence_type = Column(
        ExistingEnum(OrderSlaConsequenceType, name="order_sla_consequence_type"),
        nullable=False,
    )
    amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(8), nullable=False)
    billing_invoice_id = Column(GUID(), nullable=True)
    billing_refund_id = Column(GUID(), nullable=True)
    ledger_tx_id = Column(GUID(), nullable=True)
    status = Column(
        ExistingEnum(OrderSlaConsequenceStatus, name="order_sla_consequence_status"),
        nullable=False,
    )
    dedupe_key = Column(String(256), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    audit_event_id = Column(GUID(), nullable=False)


class MarketplaceSlaNotificationOutbox(Base):
    __tablename__ = "marketplace_sla_notification_outbox"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    order_id = Column(String(64), nullable=False, index=True)
    client_id = Column(String(64), nullable=True, index=True)
    partner_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False)
    payload_redacted = Column(JSON_TYPE, nullable=True)
    status = Column(
        ExistingEnum(MarketplaceSlaNotificationStatus, name="marketplace_sla_notification_status"),
        nullable=False,
    )
    dedupe_key = Column(String(256), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    audit_event_id = Column(GUID(), nullable=True)


class MarketplaceOrderSlaImmutableError(ValueError):
    """Raised when a WORM marketplace SLA record is mutated."""


@event.listens_for(MarketplaceOrderContractLink, "before_update")
@event.listens_for(MarketplaceOrderContractLink, "before_delete")
@event.listens_for(MarketplaceOrderEvent, "before_update")
@event.listens_for(MarketplaceOrderEvent, "before_delete")
@event.listens_for(OrderSlaEvaluation, "before_update")
@event.listens_for(OrderSlaEvaluation, "before_delete")
@event.listens_for(OrderSlaConsequence, "before_update")
@event.listens_for(OrderSlaConsequence, "before_delete")
def _block_marketplace_sla_mutation(mapper, connection, target) -> None:
    raise MarketplaceOrderSlaImmutableError("marketplace_sla_immutable")


__all__ = [
    "MarketplaceOrderContractLink",
    "MarketplaceOrderEvent",
    "MarketplaceOrderSlaImmutableError",
    "MarketplaceSlaNotificationOutbox",
    "MarketplaceSlaNotificationStatus",
    "OrderSlaConsequence",
    "OrderSlaConsequenceStatus",
    "OrderSlaConsequenceType",
    "OrderSlaEvaluation",
    "OrderSlaSeverity",
    "OrderSlaStatus",
]
