from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from .base import TimestampMixin, UUID_LEN, UUIDPrimaryKeyMixin


class CRMDeal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "crm_deals"

    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True, nullable=False)
    pipeline_id: Mapped[str] = mapped_column(String(UUID_LEN), ForeignKey("crm_pipelines.id"), nullable=False)
    stage_id: Mapped[str] = mapped_column(String(UUID_LEN), ForeignKey("crm_pipeline_stages.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(Text, default="RUB", nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(UUID_LEN), nullable=True)
    partner_id: Mapped[str | None] = mapped_column(String(UUID_LEN), nullable=True)
    contact_id: Mapped[str | None] = mapped_column(String(UUID_LEN), ForeignKey("crm_contacts.id"), nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(UUID_LEN), index=True, nullable=True)
    priority: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="open", index=True, nullable=False)
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
