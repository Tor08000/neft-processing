from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from .base import UUID_LEN, UUIDPrimaryKeyMixin


class CRMAuditEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "crm_audit_events"
    __table_args__ = (
        Index("ix_crm_audit_tenant_entity", "tenant_id", "entity_type", "entity_id"),
        Index("ix_crm_audit_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(UUID_LEN), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(UUID_LEN), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
