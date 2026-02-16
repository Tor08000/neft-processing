from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from .base import UUID_LEN, UUIDPrimaryKeyMixin


class CRMPipeline(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "crm_pipelines"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_crm_pipelines_tenant_name"),)

    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    stages: Mapped[list["CRMPipelineStage"]] = relationship(back_populates="pipeline", cascade="all, delete-orphan")


class CRMPipelineStage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "crm_pipeline_stages"
    __table_args__ = (UniqueConstraint("pipeline_id", "position", name="uq_crm_pipeline_stages_position"),)

    pipeline_id: Mapped[str] = mapped_column(
        String(UUID_LEN), ForeignKey("crm_pipelines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(UUID_LEN), index=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_won: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_lost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    pipeline: Mapped[CRMPipeline] = relationship(back_populates="stages")
