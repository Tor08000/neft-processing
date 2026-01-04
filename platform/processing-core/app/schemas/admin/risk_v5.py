from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.risk_types import RiskSubjectType


class RiskV5ABAssignmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int | None = None
    client_id: str | None = None
    subject_type: RiskSubjectType
    bucket: Literal["A", "B"]
    weight: int = Field(ge=0, le=100)
    active: bool = True


class RiskV5ABAssignmentRead(RiskV5ABAssignmentCreate):
    id: str
    created_at: datetime


class RiskV5ModelActivate(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    subject_type: RiskSubjectType
    model_version: str


class RiskV5RetrainingRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shadow_limit: int = Field(default=1000, ge=1)


class RiskV5RetrainingResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    published: bool
    model_version: str | None


__all__ = [
    "RiskV5ABAssignmentCreate",
    "RiskV5ABAssignmentRead",
    "RiskV5ModelActivate",
    "RiskV5RetrainingRun",
    "RiskV5RetrainingResponse",
]
