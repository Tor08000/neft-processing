from __future__ import annotations

from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, new_uuid_str


class CaseKind(str, Enum):
    OPERATION = "operation"
    INVOICE = "invoice"
    ORDER = "order"
    SUPPORT = "support"
    DISPUTE = "dispute"
    INCIDENT = "incident"
    KPI = "kpi"
    FLEET = "fleet"
    BOOKING = "booking"


class CaseStatus(str, Enum):
    TRIAGE = "TRIAGE"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING = "WAITING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class CasePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseQueue(str, Enum):
    FRAUD_OPS = "FRAUD_OPS"
    FINANCE_OPS = "FINANCE_OPS"
    SUPPORT = "SUPPORT"
    GENERAL = "GENERAL"


class CaseSlaState(str, Enum):
    ON_TRACK = "ON_TRACK"
    WARNING = "WARNING"
    BREACHED = "BREACHED"


class CaseCommentType(str, Enum):
    USER = "user"
    SYSTEM = "system"


class CaseEventType(str, Enum):
    CASE_CREATED = "CASE_CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    CASE_CLOSED = "CASE_CLOSED"
    NOTE_UPDATED = "NOTE_UPDATED"
    ACTIONS_APPLIED = "ACTIONS_APPLIED"
    EXPORT_CREATED = "EXPORT_CREATED"
    CARD_CREATED = "CARD_CREATED"
    CARD_STATUS_CHANGED = "CARD_STATUS_CHANGED"
    GROUP_CREATED = "GROUP_CREATED"
    GROUP_MEMBER_ADDED = "GROUP_MEMBER_ADDED"
    GROUP_MEMBER_REMOVED = "GROUP_MEMBER_REMOVED"
    GROUP_ACCESS_GRANTED = "GROUP_ACCESS_GRANTED"
    GROUP_ACCESS_REVOKED = "GROUP_ACCESS_REVOKED"
    LIMIT_SET = "LIMIT_SET"
    LIMIT_REVOKED = "LIMIT_REVOKED"
    TRANSACTION_INGESTED = "TRANSACTION_INGESTED"
    TRANSACTION_IMPORTED = "TRANSACTION_IMPORTED"
    FLEET_TRANSACTIONS_INGESTED = "FLEET_TRANSACTIONS_INGESTED"
    FLEET_INGEST_FAILED = "FLEET_INGEST_FAILED"
    FUEL_LIMIT_BREACH_DETECTED = "FUEL_LIMIT_BREACH_DETECTED"
    FUEL_ANOMALY_DETECTED = "FUEL_ANOMALY_DETECTED"
    FUEL_CARD_AUTO_BLOCKED = "FUEL_CARD_AUTO_BLOCKED"
    FUEL_CARD_UNBLOCKED = "FUEL_CARD_UNBLOCKED"
    FLEET_POLICY_ACTION_APPLIED = "FLEET_POLICY_ACTION_APPLIED"
    FLEET_POLICY_ACTION_FAILED = "FLEET_POLICY_ACTION_FAILED"
    FLEET_ESCALATION_CASE_CREATED = "FLEET_ESCALATION_CASE_CREATED"
    FLEET_ACTION_POLICY_CREATED = "FLEET_ACTION_POLICY_CREATED"
    FLEET_ACTION_POLICY_DISABLED = "FLEET_ACTION_POLICY_DISABLED"
    FLEET_ALERT_STATUS_UPDATED = "FLEET_ALERT_STATUS_UPDATED"
    FLEET_NOTIFICATION_CHANNEL_CREATED = "FLEET_NOTIFICATION_CHANNEL_CREATED"
    FLEET_NOTIFICATION_CHANNEL_DISABLED = "FLEET_NOTIFICATION_CHANNEL_DISABLED"
    FLEET_NOTIFICATION_POLICY_CREATED = "FLEET_NOTIFICATION_POLICY_CREATED"
    FLEET_NOTIFICATION_POLICY_DISABLED = "FLEET_NOTIFICATION_POLICY_DISABLED"
    FLEET_NOTIFICATION_ENQUEUED = "FLEET_NOTIFICATION_ENQUEUED"
    FLEET_TELEGRAM_LINK_TOKEN_ISSUED = "FLEET_TELEGRAM_LINK_TOKEN_ISSUED"
    FLEET_TELEGRAM_BOUND = "FLEET_TELEGRAM_BOUND"
    FLEET_TELEGRAM_UNBOUND = "FLEET_TELEGRAM_UNBOUND"
    FLEET_TELEGRAM_SEND_FAILED = "FLEET_TELEGRAM_SEND_FAILED"
    SLA_ESCALATION_CASE_CREATED = "SLA_ESCALATION_CASE_CREATED"
    INVOICE_ISSUED = "INVOICE_ISSUED"
    PAYMENT_CAPTURED = "PAYMENT_CAPTURED"
    PAYMENT_REFUNDED = "PAYMENT_REFUNDED"
    INVOICE_STATUS_CHANGED = "INVOICE_STATUS_CHANGED"
    EXTERNAL_RECONCILIATION_COMPLETED = "EXTERNAL_RECONCILIATION_COMPLETED"
    SETTLEMENT_CALCULATED = "SETTLEMENT_CALCULATED"
    SETTLEMENT_APPROVED = "SETTLEMENT_APPROVED"
    PAYOUT_INITIATED = "PAYOUT_INITIATED"
    PAYOUT_CONFIRMED = "PAYOUT_CONFIRMED"
    MARKETPLACE_ORDER_CREATED = "MARKETPLACE_ORDER_CREATED"
    MARKETPLACE_ORDER_PAYMENT_PENDING = "MARKETPLACE_ORDER_PAYMENT_PENDING"
    MARKETPLACE_ORDER_PAYMENT_PAID = "MARKETPLACE_ORDER_PAYMENT_PAID"
    MARKETPLACE_ORDER_CONFIRMED = "MARKETPLACE_ORDER_CONFIRMED"
    MARKETPLACE_ORDER_DECLINED = "MARKETPLACE_ORDER_DECLINED"
    MARKETPLACE_ORDER_ACCEPTED = "MARKETPLACE_ORDER_ACCEPTED"
    MARKETPLACE_ORDER_REJECTED = "MARKETPLACE_ORDER_REJECTED"
    MARKETPLACE_ORDER_STARTED = "MARKETPLACE_ORDER_STARTED"
    MARKETPLACE_ORDER_PROGRESS_UPDATED = "MARKETPLACE_ORDER_PROGRESS_UPDATED"
    MARKETPLACE_ORDER_COMPLETED = "MARKETPLACE_ORDER_COMPLETED"
    MARKETPLACE_ORDER_FAILED = "MARKETPLACE_ORDER_FAILED"
    MARKETPLACE_ORDER_CANCELLED = "MARKETPLACE_ORDER_CANCELLED"
    BOOKING_CREATED = "BOOKING_CREATED"
    SLOT_LOCKED = "SLOT_LOCKED"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"
    BOOKING_DECLINED = "BOOKING_DECLINED"
    BOOKING_CANCELED = "BOOKING_CANCELED"
    BOOKING_STATUS_CHANGED = "BOOKING_STATUS_CHANGED"
    BOOKING_COMPLETED = "BOOKING_COMPLETED"
    SERVICE_RECORD_CREATED = "SERVICE_RECORD_CREATED"


class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    kind = Column(ExistingEnum(CaseKind, name="case_kind"), nullable=False, index=True)
    entity_type = Column(String(64), nullable=True, index=True)
    entity_id = Column(String(64), nullable=True, index=True)
    kpi_key = Column(String(64), nullable=True, index=True)
    window_days = Column(Integer, nullable=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        ExistingEnum(CaseStatus, name="case_status"),
        nullable=False,
        index=True,
        default=CaseStatus.TRIAGE,
    )
    queue = Column(
        ExistingEnum(CaseQueue, name="case_queue"),
        nullable=False,
        index=True,
        default=CaseQueue.GENERAL,
    )
    priority = Column(
        ExistingEnum(CasePriority, name="case_priority"),
        nullable=False,
        index=True,
        default=CasePriority.MEDIUM,
    )
    escalation_level = Column(Integer, nullable=False, default=0)
    first_response_due_at = Column(DateTime(timezone=True), nullable=True)
    resolve_due_at = Column(DateTime(timezone=True), nullable=True)
    client_id = Column(String(64), nullable=True, index=True)
    partner_id = Column(String(64), nullable=True, index=True)
    created_by = Column(String(128), nullable=True)
    assigned_to = Column(String(128), nullable=True)
    case_source_ref_type = Column(String(64), nullable=True, index=True)
    case_source_ref_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CaseSnapshot(Base):
    __tablename__ = "case_snapshots"

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    explain_snapshot = Column(JSON, nullable=False)
    diff_snapshot = Column(JSON, nullable=True)
    selected_actions = Column(JSON, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class CaseComment(Base):
    __tablename__ = "case_comments"

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    author = Column(String(128), nullable=True)
    type = Column(
        ExistingEnum(CaseCommentType, name="case_comment_type"),
        nullable=False,
        default=CaseCommentType.USER,
    )
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class CaseEvent(Base):
    __tablename__ = "case_events"
    __table_args__ = (UniqueConstraint("case_id", "seq", name="ux_case_events_case_seq"),)

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    seq = Column(BigInteger, nullable=False)
    at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    type = Column(ExistingEnum(CaseEventType, name="case_event_type"), nullable=False)
    actor_user_id = Column(String(128), nullable=True)
    actor_email = Column(String(256), nullable=True)
    request_id = Column(String(128), nullable=True)
    trace_id = Column(String(128), nullable=True)
    payload_redacted = Column(JSON, nullable=False)
    prev_hash = Column(Text, nullable=False)
    hash = Column(Text, nullable=False)
    signature = Column(Text, nullable=True)
    signature_alg = Column(String(64), nullable=True)
    signing_key_id = Column(String(256), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "Case",
    "CaseComment",
    "CaseCommentType",
    "CaseEvent",
    "CaseEventType",
    "CaseKind",
    "CasePriority",
    "CaseQueue",
    "CaseSnapshot",
    "CaseSlaState",
    "CaseStatus",
]
