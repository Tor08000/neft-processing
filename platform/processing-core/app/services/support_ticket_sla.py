from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.support_ticket import SupportTicket, SupportTicketSlaPolicy, SupportTicketSlaStatus
from app.services.audit_service import AuditService, RequestContext


DEFAULT_FIRST_RESPONSE_MINUTES = 120
DEFAULT_RESOLUTION_MINUTES = 1440
FIRST_RESPONSE_BREACH_EVENT = "support_sla_first_response_breached"
RESOLUTION_BREACH_EVENT = "support_sla_resolution_breached"


@dataclass(frozen=True)
class SupportTicketSlaConfig:
    first_response_minutes: int
    resolution_minutes: int


def load_support_ticket_sla_config(db, *, org_id: str) -> SupportTicketSlaConfig:
    policy = db.query(SupportTicketSlaPolicy).filter(SupportTicketSlaPolicy.org_id == org_id).one_or_none()
    if policy:
        return SupportTicketSlaConfig(
            first_response_minutes=policy.first_response_minutes,
            resolution_minutes=policy.resolution_minutes,
        )
    return SupportTicketSlaConfig(
        first_response_minutes=DEFAULT_FIRST_RESPONSE_MINUTES,
        resolution_minutes=DEFAULT_RESOLUTION_MINUTES,
    )


def initialize_support_ticket_sla(ticket: SupportTicket, config: SupportTicketSlaConfig) -> None:
    now = datetime.now(timezone.utc)
    ticket.first_response_due_at = now + timedelta(minutes=config.first_response_minutes)
    ticket.resolution_due_at = now + timedelta(minutes=config.resolution_minutes)
    ticket.sla_first_response_status = SupportTicketSlaStatus.PENDING
    ticket.sla_resolution_status = SupportTicketSlaStatus.PENDING


def sla_remaining_minutes(*, due_at: datetime | None, reference_time: datetime | None = None) -> int | None:
    if not due_at:
        return None
    now = reference_time or datetime.now(timezone.utc)
    delta = due_at - now
    return int(delta.total_seconds() // 60)


def _status_from_due(due_at: datetime | None, occurred_at: datetime) -> SupportTicketSlaStatus:
    if not due_at:
        return SupportTicketSlaStatus.OK
    if occurred_at > due_at:
        return SupportTicketSlaStatus.BREACHED
    return SupportTicketSlaStatus.OK


def _audit_breach(
    audit: AuditService,
    *,
    event_type: str,
    ticket: SupportTicket,
    request_ctx: RequestContext | None,
) -> None:
    audit.audit(
        event_type=event_type,
        entity_type="support_ticket",
        entity_id=str(ticket.id),
        action=event_type,
        request_ctx=request_ctx,
        after={"status": ticket.status.value},
    )


def mark_first_response(ticket: SupportTicket, *, audit: AuditService, request_ctx: RequestContext | None) -> None:
    if ticket.first_response_at:
        return
    now = datetime.now(timezone.utc)
    ticket.first_response_at = now
    status = _status_from_due(ticket.first_response_due_at, now)
    previous = ticket.sla_first_response_status
    ticket.sla_first_response_status = status
    if previous == SupportTicketSlaStatus.PENDING and status == SupportTicketSlaStatus.BREACHED:
        _audit_breach(audit, event_type=FIRST_RESPONSE_BREACH_EVENT, ticket=ticket, request_ctx=request_ctx)


def mark_resolution(ticket: SupportTicket, *, audit: AuditService, request_ctx: RequestContext | None) -> None:
    if not ticket.resolved_at:
        ticket.resolved_at = datetime.now(timezone.utc)
    status = _status_from_due(ticket.resolution_due_at, ticket.resolved_at)
    previous = ticket.sla_resolution_status
    if previous != SupportTicketSlaStatus.BREACHED:
        ticket.sla_resolution_status = status
    if previous == SupportTicketSlaStatus.PENDING and ticket.sla_resolution_status == SupportTicketSlaStatus.BREACHED:
        _audit_breach(audit, event_type=RESOLUTION_BREACH_EVENT, ticket=ticket, request_ctx=request_ctx)


def refresh_sla_breaches(
    ticket: SupportTicket,
    *,
    now: datetime,
    audit: AuditService,
    request_ctx: RequestContext | None,
) -> list[str]:
    breached_events: list[str] = []
    if (
        ticket.sla_first_response_status == SupportTicketSlaStatus.PENDING
        and ticket.first_response_due_at
        and now > ticket.first_response_due_at
    ):
        ticket.sla_first_response_status = SupportTicketSlaStatus.BREACHED
        _audit_breach(audit, event_type=FIRST_RESPONSE_BREACH_EVENT, ticket=ticket, request_ctx=request_ctx)
        breached_events.append(FIRST_RESPONSE_BREACH_EVENT)
    if (
        ticket.sla_resolution_status == SupportTicketSlaStatus.PENDING
        and ticket.resolution_due_at
        and now > ticket.resolution_due_at
    ):
        ticket.sla_resolution_status = SupportTicketSlaStatus.BREACHED
        _audit_breach(audit, event_type=RESOLUTION_BREACH_EVENT, ticket=ticket, request_ctx=request_ctx)
        breached_events.append(RESOLUTION_BREACH_EVENT)
    return breached_events


__all__ = [
    "DEFAULT_FIRST_RESPONSE_MINUTES",
    "DEFAULT_RESOLUTION_MINUTES",
    "SupportTicketSlaConfig",
    "initialize_support_ticket_sla",
    "load_support_ticket_sla_config",
    "mark_first_response",
    "mark_resolution",
    "refresh_sla_breaches",
    "sla_remaining_minutes",
]
