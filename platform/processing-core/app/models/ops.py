from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Integer, JSON, String, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.models.unified_explain import PrimaryReason


class OpsEscalationTarget(str, Enum):
    CRM = "CRM"
    COMPLIANCE = "COMPLIANCE"
    LOGISTICS = "LOGISTICS"
    FINANCE = "FINANCE"


class OpsEscalationStatus(str, Enum):
    OPEN = "OPEN"
    ACK = "ACK"
    CLOSED = "CLOSED"


class OpsEscalationPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OpsEscalationSource(str, Enum):
    AUTO_SLA_EXPIRED = "AUTO_SLA_EXPIRED"
    MANUAL_FROM_EXPLAIN = "MANUAL_FROM_EXPLAIN"
    SYSTEM = "SYSTEM"


class OpsEscalation(Base):
    __tablename__ = "ops_escalations"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ops_escalations_idempotency_key"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=True, index=True)
    target = Column(
        ExistingEnum(OpsEscalationTarget, name="ops_escalation_target"),
        nullable=False,
        index=True,
    )
    status = Column(
        ExistingEnum(OpsEscalationStatus, name="ops_escalation_status"),
        nullable=False,
        index=True,
        default=OpsEscalationStatus.OPEN,
    )
    priority = Column(
        ExistingEnum(OpsEscalationPriority, name="ops_escalation_priority"),
        nullable=False,
        index=True,
        default=OpsEscalationPriority.MEDIUM,
    )
    primary_reason = Column(
        ExistingEnum(PrimaryReason, name="ops_escalation_primary_reason"),
        nullable=False,
        index=True,
    )
    subject_type = Column(String(64), nullable=False, index=True)
    subject_id = Column(String(128), nullable=False, index=True)
    source = Column(
        ExistingEnum(OpsEscalationSource, name="ops_escalation_source"),
        nullable=False,
        index=True,
    )
    sla_started_at = Column(DateTime(timezone=True), nullable=True)
    sla_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    acked_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_by_actor_type = Column(String(32), nullable=True)
    created_by_actor_id = Column(String(64), nullable=True)
    created_by_actor_email = Column(String(128), nullable=True)
    meta = Column(JSON, nullable=True)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)


__all__ = [
    "OpsEscalation",
    "OpsEscalationPriority",
    "OpsEscalationSource",
    "OpsEscalationStatus",
    "OpsEscalationTarget",
]
