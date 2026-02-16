from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from .base import TimestampMixin, UUID_LEN, UUIDPrimaryKeyMixin


class CRMTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "crm_tasks"

    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True, nullable=False)
    deal_id: Mapped[str | None] = mapped_column(String(UUID_LEN), ForeignKey("crm_deals.id", ondelete="SET NULL"), nullable=True)
    contact_id: Mapped[str | None] = mapped_column(
        String(UUID_LEN), ForeignKey("crm_contacts.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, default="open", nullable=False)
    assignee_user_id: Mapped[str | None] = mapped_column(String(UUID_LEN), index=True, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(UUID_LEN), nullable=True)
