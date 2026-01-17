from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, JSON, UniqueConstraint, func
from sqlalchemy.dialects import postgresql

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class ServiceSloService(str, Enum):
    EXPORTS = "exports"
    EMAIL = "email"
    SUPPORT = "support"
    SCHEDULES = "schedules"


class ServiceSloMetric(str, Enum):
    LATENCY = "latency"
    SUCCESS_RATE = "success_rate"


class ServiceSloWindow(str, Enum):
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"


class ServiceSloBreachStatus(str, Enum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    RESOLVED = "RESOLVED"


JSONB_TYPE = postgresql.JSONB(none_as_null=True)
JSON_TYPE = JSON().with_variant(JSONB_TYPE, "postgresql")


class ServiceSlo(Base):
    __tablename__ = "service_slo"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(GUID(), nullable=False, index=True)
    service = Column(ExistingEnum(ServiceSloService, name="service_slo_service"), nullable=False)
    metric = Column(ExistingEnum(ServiceSloMetric, name="service_slo_metric"), nullable=False)
    objective_json = Column(JSON_TYPE, nullable=False)
    window = Column(ExistingEnum(ServiceSloWindow, name="service_slo_window"), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, onupdate=func.now())

    __table_args__ = (
        Index("ix_service_slo_org_enabled", "org_id", "enabled"),
        Index("ix_service_slo_service", "service", "metric"),
    )


class ServiceSloBreach(Base):
    __tablename__ = "service_slo_breaches"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    slo_id = Column(GUID(), ForeignKey("service_slo.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id = Column(GUID(), nullable=False, index=True)
    service = Column(ExistingEnum(ServiceSloService, name="service_slo_service"), nullable=False)
    metric = Column(ExistingEnum(ServiceSloMetric, name="service_slo_metric"), nullable=False)
    window = Column(ExistingEnum(ServiceSloWindow, name="service_slo_window"), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    observed_value_json = Column(JSON_TYPE, nullable=True)
    breached_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(ExistingEnum(ServiceSloBreachStatus, name="service_slo_breach_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("slo_id", "window_start", "window_end", name="uq_service_slo_window"),
        Index("ix_service_slo_breaches_org_status", "org_id", "status"),
        Index("ix_service_slo_breaches_window", "window", "window_end"),
    )


__all__ = [
    "ServiceSlo",
    "ServiceSloBreach",
    "ServiceSloBreachStatus",
    "ServiceSloMetric",
    "ServiceSloService",
    "ServiceSloWindow",
]
