from __future__ import annotations

from sqlalchemy import Boolean, Column, Index, Integer, String

from app.db import Base
from app.db.types import ExistingEnum
from app.models.risk_types import RiskSubjectType


class RiskPolicy(Base):
    __tablename__ = "risk_policies"

    id = Column(String(64), primary_key=True)
    subject_type = Column(ExistingEnum(RiskSubjectType, name="risksubjecttype"), nullable=False)

    tenant_id = Column(Integer, nullable=True)
    client_id = Column(String(64), nullable=True)
    provider = Column(String(64), nullable=True)
    currency = Column(String(3), nullable=True)
    country = Column(String(2), nullable=True)

    threshold_set_id = Column(String(64), nullable=False)
    model_selector = Column(String(64), nullable=False)

    priority = Column(Integer, nullable=False, default=100)
    active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_risk_policies_subject", "subject_type"),
        Index("ix_risk_policies_active", "active"),
        Index("ix_risk_policies_priority", "priority"),
        Index("ix_risk_policies_tenant", "tenant_id"),
        Index("ix_risk_policies_client", "client_id"),
    )


__all__ = ["RiskPolicy"]
