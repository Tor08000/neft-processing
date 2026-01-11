from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from app.db import Base


class PriceVersionStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ACTIVE = "ACTIVE"
    ROLLED_BACK = "ROLLED_BACK"
    ARCHIVED = "ARCHIVED"


class PriceScheduleStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PriceVersion(Base):
    __tablename__ = "price_versions"

    id = Column(String(36), primary_key=True)
    name = Column(String(128), nullable=False)
    status = Column(SAEnum(PriceVersionStatus, name="price_version_status"), nullable=False)
    notes = Column(String(512), nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)


class PriceVersionItem(Base):
    __tablename__ = "price_version_items"
    __table_args__ = (
        UniqueConstraint(
            "price_version_id",
            "plan_code",
            "billing_period",
            "currency",
            name="uq_price_version_item",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    price_version_id = Column(String(36), ForeignKey("price_versions.id"), nullable=False, index=True)
    plan_code = Column(String(64), nullable=False, index=True)
    billing_period = Column(String(16), nullable=False)
    currency = Column(String(3), nullable=False)
    base_price = Column(Numeric(18, 6), nullable=False)
    setup_fee = Column(Numeric(18, 6), nullable=True)
    meta = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PriceSchedule(Base):
    __tablename__ = "price_schedules"

    id = Column(String(36), primary_key=True)
    price_version_id = Column(String(36), ForeignKey("price_versions.id"), nullable=False, index=True)
    effective_from = Column(DateTime(timezone=True), nullable=False)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    priority = Column(Integer, nullable=False, server_default="0")
    status = Column(SAEnum(PriceScheduleStatus, name="price_schedule_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PriceVersionAudit(Base):
    __tablename__ = "price_version_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    price_version_id = Column(String(36), ForeignKey("price_versions.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    actor_id = Column(String(64), nullable=True)
    payload = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "PriceVersionStatus",
    "PriceScheduleStatus",
    "PriceVersion",
    "PriceVersionItem",
    "PriceSchedule",
    "PriceVersionAudit",
]
