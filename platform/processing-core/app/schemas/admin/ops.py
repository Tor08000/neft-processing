from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.ops import (
    OpsEscalationPriority,
    OpsEscalationSource,
    OpsEscalationStatus,
    OpsEscalationTarget,
)
from app.models.unified_explain import PrimaryReason


class OpsEscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: int
    client_id: str | None
    target: OpsEscalationTarget
    status: OpsEscalationStatus
    priority: OpsEscalationPriority
    primary_reason: PrimaryReason
    subject_type: str
    subject_id: str
    source: OpsEscalationSource
    sla_started_at: datetime | None
    sla_expires_at: datetime | None
    created_at: datetime
    acked_at: datetime | None
    closed_at: datetime | None
    created_by_actor_type: str | None
    created_by_actor_id: str | None
    created_by_actor_email: str | None
    meta: dict | None


class OpsEscalationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OpsEscalationOut]
    total: int
    limit: int
    offset: int


class OpsEscalationScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: int


__all__ = ["OpsEscalationListResponse", "OpsEscalationOut", "OpsEscalationScanResponse"]
