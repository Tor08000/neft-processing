from __future__ import annotations

from sqlalchemy import JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from .base import TimestampMixin, UUID_LEN, UUIDPrimaryKeyMixin


class CRMContact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "crm_contacts"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_crm_contacts_tenant_email"),)

    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True, nullable=False)
    partner_id: Mapped[str | None] = mapped_column(String(UUID_LEN), index=True, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(UUID_LEN), index=True, nullable=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
