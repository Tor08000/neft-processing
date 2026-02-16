from __future__ import annotations

import uuid

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

UUID_LEN = 36


class CRMContact(Base):
    __tablename__ = "crm_contacts"
    id: Mapped[str] = mapped_column(String(UUID_LEN), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    owner_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CRMPipeline(Base):
    __tablename__ = "crm_pipelines"
    id: Mapped[str] = mapped_column(String(UUID_LEN), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CRMStage(Base):
    __tablename__ = "crm_stages"
    id: Mapped[str] = mapped_column(String(UUID_LEN), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id: Mapped[str] = mapped_column(String(UUID_LEN), ForeignKey("crm_pipelines.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    probability: Mapped[int] = mapped_column(Integer)


class CRMDeal(Base):
    __tablename__ = "crm_deals"
    id: Mapped[str] = mapped_column(String(UUID_LEN), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    contact_id: Mapped[str | None] = mapped_column(String(UUID_LEN), ForeignKey("crm_contacts.id"), nullable=True)
    pipeline_id: Mapped[str] = mapped_column(String(UUID_LEN), ForeignKey("crm_pipelines.id"))
    stage_id: Mapped[str] = mapped_column(String(UUID_LEN), ForeignKey("crm_stages.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(16), default="USD")
    status: Mapped[str] = mapped_column(String(16), default="open")
    owner_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    expected_close_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CRMTask(Base):
    __tablename__ = "crm_tasks"
    id: Mapped[str] = mapped_column(String(UUID_LEN), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    related_type: Mapped[str] = mapped_column(String(32))
    related_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    assigned_to: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    created_by: Mapped[str] = mapped_column(String(UUID_LEN))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CRMComment(Base):
    __tablename__ = "crm_comments"
    id: Mapped[str] = mapped_column(String(UUID_LEN), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    related_type: Mapped[str] = mapped_column(String(32))
    related_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    message: Mapped[str] = mapped_column(Text)
    author_id: Mapped[str] = mapped_column(String(UUID_LEN))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CRMAuditLog(Base):
    __tablename__ = "crm_audit_log"
    id: Mapped[str] = mapped_column(String(UUID_LEN), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    action: Mapped[str] = mapped_column(String(32))
    old_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor_id: Mapped[str] = mapped_column(String(UUID_LEN))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(String(UUID_LEN), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
