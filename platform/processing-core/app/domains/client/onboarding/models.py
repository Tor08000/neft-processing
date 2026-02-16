from __future__ import annotations

import enum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.db.types import GUID


class OnboardingApplicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ClientOnboardingApplication(Base):
    __tablename__ = "client_onboarding_applications"
    __table_args__ = (
        Index("ix_client_onboarding_applications_lower_email", text("lower(email)")),
        Index("ix_client_onboarding_applications_status", "status"),
        Index("ix_client_onboarding_applications_created_at", "created_at"),
        Index("ix_client_onboarding_applications_created_by_user_id", "created_by_user_id"),
        Index("ix_client_onboarding_applications_inn", "inn"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String, nullable=True)
    inn: Mapped[str | None] = mapped_column(String, nullable=True)
    ogrn: Mapped[str | None] = mapped_column(String, nullable=True)
    org_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default=OnboardingApplicationStatus.DRAFT.value)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    submitted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("clients.id"), nullable=True)
    approved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
