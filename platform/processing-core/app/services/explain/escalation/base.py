from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.unified_explain import PrimaryReason
from app.models.audit_log import ActorType
from app.services.audit_service import AuditService, RequestContext
from app.services.explain.sla import SLA_DEFINITIONS, SLAClock


class EscalationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    status: Literal["PENDING"]


ESCALATION_MAP = {
    PrimaryReason.LIMIT: "CRM",
    PrimaryReason.RISK: "COMPLIANCE",
    PrimaryReason.LOGISTICS: "LOGISTICS",
    PrimaryReason.MONEY: "FINANCE",
}


def build_escalation(primary_reason: PrimaryReason) -> EscalationInfo | None:
    target = ESCALATION_MAP.get(primary_reason)
    if not target:
        return None
    return EscalationInfo(target=target, status="PENDING")


def _audit_payload(primary_reason: PrimaryReason, target: str | None) -> dict[str, str | int | None]:
    sla_definition = SLA_DEFINITIONS.get(primary_reason)
    return {
        "primary_reason": primary_reason.value,
        "target": target,
        "sla_minutes": sla_definition.timeout_minutes if sla_definition else None,
    }


def audit_primary_reason_assigned(
    audit: AuditService,
    *,
    entity_type: str,
    entity_id: str,
    tenant_id: int | None,
    primary_reason: PrimaryReason,
    target: str | None,
) -> None:
    audit.audit(
        event_type="PRIMARY_REASON_ASSIGNED",
        entity_type=entity_type,
        entity_id=entity_id,
        action="ASSIGN",
        after=_audit_payload(primary_reason, target),
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM, tenant_id=tenant_id),
    )


def audit_primary_reason_escalated(
    audit: AuditService,
    *,
    entity_type: str,
    entity_id: str,
    tenant_id: int | None,
    primary_reason: PrimaryReason,
    target: str | None,
) -> None:
    audit.audit(
        event_type="PRIMARY_REASON_ESCALATED",
        entity_type=entity_type,
        entity_id=entity_id,
        action="ESCALATE",
        after=_audit_payload(primary_reason, target),
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM, tenant_id=tenant_id),
    )


def audit_sla_expired(
    audit: AuditService,
    *,
    entity_type: str,
    entity_id: str,
    tenant_id: int | None,
    primary_reason: PrimaryReason,
    target: str | None,
    sla: SLAClock | None,
) -> None:
    if not sla or sla.remaining_minutes > 0:
        return
    audit.audit(
        event_type="SLA_EXPIRED",
        entity_type=entity_type,
        entity_id=entity_id,
        action="EXPIRE",
        after=_audit_payload(primary_reason, target),
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM, tenant_id=tenant_id),
    )


__all__ = [
    "ESCALATION_MAP",
    "EscalationInfo",
    "audit_primary_reason_assigned",
    "audit_primary_reason_escalated",
    "audit_sla_expired",
    "build_escalation",
]
