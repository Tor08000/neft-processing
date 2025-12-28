from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field, Field

from app.models.ops import (
    OpsEscalationPriority,
    OpsEscalationSource,
    OpsEscalationStatus,
    OpsEscalationTarget,
)
from app.models.unified_explain import PrimaryReason
from app.services.explain.sla import SLA_DEFINITIONS


class OpsEscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: int
    client_id: str | None
    target: OpsEscalationTarget
    status: OpsEscalationStatus
    priority: OpsEscalationPriority
    primary_reason: PrimaryReason
    reason_code: str
    subject_type: str
    subject_id: str
    source: OpsEscalationSource
    sla_started_at: datetime | None
    sla_expires_at: datetime | None
    created_at: datetime
    acked_at: datetime | None
    acked_by: str | None
    ack_reason_code: str | None
    ack_reason_text: str | None
    closed_at: datetime | None
    closed_by: str | None
    close_reason_code: str | None
    close_reason_text: str | None
    created_by_actor_type: str | None
    created_by_actor_id: str | None
    created_by_actor_email: str | None
    unified_explain_snapshot_hash: str | None
    unified_explain_snapshot: dict[str, Any] | None
    meta: dict | None

    def _ensure_timezone(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @computed_field
    @property
    def sla_due_at(self) -> datetime | None:
        if self.sla_expires_at:
            return self._ensure_timezone(self.sla_expires_at)
        if not self.sla_started_at:
            return None
        definition = SLA_DEFINITIONS.get(self.primary_reason)
        if not definition:
            return None
        return self._ensure_timezone(self.sla_started_at) + timedelta(minutes=definition.timeout_minutes)

    @computed_field
    @property
    def sla_overdue(self) -> bool:
        if not self.sla_due_at or self.status == OpsEscalationStatus.CLOSED:
            return False
        now = datetime.now(timezone.utc)
        return now > self._ensure_timezone(self.sla_due_at)

    @computed_field
    @property
    def sla_elapsed_seconds(self) -> int | None:
        if not self.sla_started_at:
            return None
        now = datetime.now(timezone.utc)
        return int((now - self._ensure_timezone(self.sla_started_at)).total_seconds())


class OpsEscalationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OpsEscalationOut]
    total: int
    limit: int
    offset: int


class OpsEscalationScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: int


class OpsEscalationActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(min_length=1)
    reason_text: str | None = None


class OpsEscalationSLAReportReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    overdue: int


class OpsEscalationSLAReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str
    total: int
    closed_within_sla: int
    overdue: int
    by_primary_reason: dict[PrimaryReason, OpsEscalationSLAReportReason]


class OpsKpiReasonStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open: int
    sla_violations: int | None = None
    avg_resolution_hours: float | None = None


class OpsKpiTeamStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open: int


class OpsKpiResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by_reason: dict[str, OpsKpiReasonStats]
    by_team: dict[str, OpsKpiTeamStats]


__all__ = [
    "OpsEscalationActionRequest",
    "OpsEscalationListResponse",
    "OpsEscalationOut",
    "OpsEscalationScanResponse",
    "OpsEscalationSLAReport",
    "OpsEscalationSLAReportReason",
    "OpsKpiReasonStats",
    "OpsKpiResponse",
    "OpsKpiTeamStats",
]
