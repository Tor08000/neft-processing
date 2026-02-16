from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from .base import UUID_LEN, UUIDPrimaryKeyMixin


class CRMComment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "crm_comments"
    __table_args__ = (Index("ix_crm_comments_tenant_entity", "tenant_id", "entity_type", "entity_id"),)

    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(UUID_LEN), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(String(UUID_LEN), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
