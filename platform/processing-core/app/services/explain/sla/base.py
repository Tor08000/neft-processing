from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, ConfigDict

from app.models.unified_explain import PrimaryReason


class SLADefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_reason: PrimaryReason
    timeout_minutes: int
    escalation_target: str


class SLAClock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    started_at: str
    expires_at: str
    remaining_minutes: int


SLA_DEFINITIONS: dict[PrimaryReason, SLADefinition] = {
    PrimaryReason.LIMIT: SLADefinition(
        primary_reason=PrimaryReason.LIMIT,
        timeout_minutes=1440,
        escalation_target="CRM",
    ),
    PrimaryReason.RISK: SLADefinition(
        primary_reason=PrimaryReason.RISK,
        timeout_minutes=120,
        escalation_target="COMPLIANCE",
    ),
    PrimaryReason.LOGISTICS: SLADefinition(
        primary_reason=PrimaryReason.LOGISTICS,
        timeout_minutes=60,
        escalation_target="OPS",
    ),
    PrimaryReason.MONEY: SLADefinition(
        primary_reason=PrimaryReason.MONEY,
        timeout_minutes=240,
        escalation_target="FINANCE",
    ),
}


def build_sla(
    primary_reason: PrimaryReason,
    *,
    started_at: datetime | None,
    now: datetime | None = None,
) -> SLAClock | None:
    definition = SLA_DEFINITIONS.get(primary_reason)
    if not definition or not started_at:
        return None

    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    expires_at = started_at + timedelta(minutes=definition.timeout_minutes)
    remaining_seconds = (expires_at - current_time).total_seconds()
    remaining_minutes = max(0, int(remaining_seconds // 60))
    remaining_minutes = min(definition.timeout_minutes, remaining_minutes)

    return SLAClock(
        started_at=started_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        expires_at=expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        remaining_minutes=remaining_minutes,
    )


__all__ = ["SLAClock", "SLADefinition", "SLA_DEFINITIONS", "build_sla"]
