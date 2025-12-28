from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.models.risk_types import RiskSubjectType


class RiskV5ABAssignment(Base):
    __tablename__ = "risk_v5_ab_assignments"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=True)
    client_id = Column(String(64), nullable=True)
    subject_type = Column(ExistingEnum(RiskSubjectType, name="risksubjecttype"), nullable=False)
    bucket = Column(String(1), nullable=False)
    weight = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_risk_v5_ab_assignments_subject", "subject_type"),
        Index("ix_risk_v5_ab_assignments_client", "client_id"),
        Index("ix_risk_v5_ab_assignments_tenant", "tenant_id"),
        Index("ix_risk_v5_ab_assignments_active", "active"),
    )


__all__ = ["RiskV5ABAssignment"]
