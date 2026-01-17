from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.celery_client import celery_client
from app.models.audit_log import ActorType, AuditVisibility
from app.models.helpdesk import (
    HelpdeskInboundEventStatus,
    HelpdeskIntegration,
    HelpdeskIntegrationStatus,
    HelpdeskOutbox,
    HelpdeskOutboxEventType,
    HelpdeskOutboxStatus,
    HelpdeskProvider,
    HelpdeskTicketLink,
    HelpdeskTicketLinkStatus,
)
from app.models.support_ticket import (
    SupportTicket,
    SupportTicketAttachment,
    SupportTicketComment,
    SupportTicketStatus,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.client_notifications import ADMIN_TARGET_ROLES, ClientNotificationSeverity, create_notification
from app.services.email_service import build_idempotency_key
from app.services.email_templates import build_portal_url
from app.services.support_ticket_sla import mark_first_response, mark_resolution

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
RETRY_DELAYS = [60, 300, 900, 3600, 3600, 3600]
FAILURE_NOTIFICATION_THRESHOLD = 3
HELPDESK_INBOUND_SOURCE = "HELPDESK_INBOUND"
HELPDESK_INBOUND_ACTOR_ID = "helpdesk_inbound"


@dataclass(frozen=True)
class HelpdeskAuthor:
    name: str | None
    email: str | None
    role: str | None


@dataclass(frozen=True)
class HelpdeskComment:
    body: str
    is_public: bool | None
    created_at: str | None


@dataclass(frozen=True)
class HelpdeskStatusChange:
    from_status: str | None
    to_status: str | None


@dataclass(frozen=True)
class NormalizedHelpdeskEvent:
    event_id: str
    event_type: str
    external_ticket_id: str
    author: HelpdeskAuthor | None = None
    comment: HelpdeskComment | None = None
    status: HelpdeskStatusChange | None = None


@dataclass(frozen=True)
class ExternalTicketRef:
    external_ticket_id: str
    external_url: str | None = None


class HelpdeskProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class HelpdeskProvider:
    def create_ticket(self, payload: dict[str, Any]) -> ExternalTicketRef:
        raise NotImplementedError

    def add_comment(self, external_ticket_id: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    def close_ticket(self, external_ticket_id: str) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class ZendeskConfig:
    base_url: str
    api_email: str
    api_token: str
    brand_id: str | None = None


class ZendeskProvider(HelpdeskProvider):
    def __init__(self, config: ZendeskConfig) -> None:
        self._config = config

    def _auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(f"{self._config.api_email}/token", self._config.api_token)

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._config.base_url.rstrip('/')}{path}"
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.request(method, url, json=json, auth=self._auth())
                response.raise_for_status()
                if response.content:
                    return response.json()
                return {}
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            retryable = status >= 500
            raise HelpdeskProviderError(f"zendesk_http_{status}", retryable=retryable) from exc
        except httpx.RequestError as exc:
            raise HelpdeskProviderError("zendesk_unavailable", retryable=True) from exc
        except Exception as exc:  # noqa: BLE001
            raise HelpdeskProviderError("zendesk_error", retryable=True) from exc

    def create_ticket(self, payload: dict[str, Any]) -> ExternalTicketRef:
        priority_map = {
            "LOW": "low",
            "NORMAL": "normal",
            "HIGH": "high",
        }
        priority = priority_map.get(payload.get("priority") or "", "normal")
        ticket_payload: dict[str, Any] = {
            "subject": payload.get("subject") or "Support ticket",
            "comment": {"body": payload.get("description") or ""},
            "priority": priority,
            "tags": payload.get("tags") or [],
        }
        requester_email = payload.get("requester_email")
        if requester_email:
            ticket_payload["requester"] = {"email": requester_email}
        if self._config.brand_id:
            ticket_payload["brand_id"] = self._config.brand_id

        response = self._request("POST", "/api/v2/tickets.json", json={"ticket": ticket_payload})
        ticket = response.get("ticket") or {}
        ticket_id = str(ticket.get("id") or "")
        if not ticket_id:
            raise HelpdeskProviderError("zendesk_missing_ticket_id", retryable=False)
        external_url = f"{self._config.base_url.rstrip('/')}/agent/tickets/{ticket_id}"
        return ExternalTicketRef(external_ticket_id=ticket_id, external_url=external_url)

    def add_comment(self, external_ticket_id: str, payload: dict[str, Any]) -> None:
        comment_body = payload.get("comment") or ""
        self._request(
            "PUT",
            f"/api/v2/tickets/{external_ticket_id}.json",
            json={"ticket": {"comment": {"body": comment_body}}},
        )

    def close_ticket(self, external_ticket_id: str) -> None:
        self._request(
            "PUT",
            f"/api/v2/tickets/{external_ticket_id}.json",
            json={"ticket": {"status": "solved"}},
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def _provider_from_integration(integration: HelpdeskIntegration) -> HelpdeskProvider:
    config = integration.config_json or {}
    if integration.provider == HelpdeskProvider.ZENDESK:
        base_url = config.get("base_url")
        api_email = config.get("api_email")
        api_token = config.get("api_token")
        if not base_url or not api_email or not api_token:
            raise HelpdeskProviderError("zendesk_missing_config", retryable=False)
        return ZendeskProvider(
            ZendeskConfig(
                base_url=_normalize_base_url(str(base_url)),
                api_email=str(api_email),
                api_token=str(api_token),
                brand_id=str(config.get("brand_id")) if config.get("brand_id") else None,
            )
        )
    raise HelpdeskProviderError("provider_not_supported", retryable=False)


def get_active_integration(db: Session, *, org_id: str) -> HelpdeskIntegration | None:
    return (
        db.query(HelpdeskIntegration)
        .filter(HelpdeskIntegration.org_id == org_id)
        .filter(HelpdeskIntegration.status == HelpdeskIntegrationStatus.ACTIVE)
        .one_or_none()
    )


def get_integration(db: Session, *, org_id: str) -> HelpdeskIntegration | None:
    return db.query(HelpdeskIntegration).filter(HelpdeskIntegration.org_id == org_id).one_or_none()


def upsert_integration(
    db: Session,
    *,
    org_id: str,
    provider: HelpdeskProvider,
    config: dict[str, Any],
    status: HelpdeskIntegrationStatus,
) -> HelpdeskIntegration:
    integration = (
        db.query(HelpdeskIntegration)
        .filter(HelpdeskIntegration.org_id == org_id)
        .filter(HelpdeskIntegration.provider == provider)
        .one_or_none()
    )
    if integration:
        integration.config_json = config
        integration.status = status
        integration.updated_at = _now()
        return integration
    integration = HelpdeskIntegration(
        org_id=org_id,
        provider=provider,
        status=status,
        config_json=config,
    )
    db.add(integration)
    return integration


def _safe_config_values(config: dict[str, Any] | None) -> dict[str, Any]:
    if not config:
        return {}
    return {
        "base_url": config.get("base_url"),
        "project_id": config.get("project_id"),
        "brand_id": config.get("brand_id"),
    }


def _format_ticket_description(payload: dict[str, Any]) -> str:
    lines = [payload.get("description") or ""]
    if payload.get("portal_url"):
        lines.append("")
        lines.append(f"Portal: {payload['portal_url']}")
    if payload.get("internal_ticket_id"):
        lines.append(f"Internal ticket: {payload['internal_ticket_id']}")
    if payload.get("org_id"):
        lines.append(f"Org: {payload['org_id']}")
    if payload.get("created_by_email"):
        lines.append(f"Requester email: {payload['created_by_email']}")
    attachments = payload.get("attachments") or []
    if attachments:
        lines.append("")
        lines.append("Attachments:")
        for attachment in attachments:
            name = attachment.get("file_name") or "attachment"
            url = attachment.get("download_url")
            if url:
                lines.append(f"- {name}: {url}")
            else:
                lines.append(f"- {name}")
    return "\n".join(line for line in lines if line is not None)


def _format_comment(payload: dict[str, Any]) -> str:
    lines = [payload.get("message") or ""]
    author = payload.get("author_email")
    if author:
        lines.append("")
        lines.append(f"Author: {author}")
    created_at = payload.get("created_at")
    if created_at:
        lines.append(f"At: {created_at}")
    if payload.get("portal_url"):
        lines.append(f"Portal: {payload['portal_url']}")
    return "\n".join(line for line in lines if line is not None)


def _next_retry_delay(attempts: int) -> int | None:
    if attempts <= 0:
        return RETRY_DELAYS[0]
    if attempts - 1 < len(RETRY_DELAYS):
        return RETRY_DELAYS[attempts - 1]
    return None


def _audit_outbox_event(
    db: Session,
    *,
    event_type: str,
    outbox: HelpdeskOutbox,
    error: str | None = None,
) -> None:
    ctx = RequestContext(actor_type=ActorType.SERVICE, actor_id="helpdesk_worker")
    AuditService(db).audit(
        event_type=event_type,
        entity_type="helpdesk_outbox",
        entity_id=str(outbox.id),
        action=event_type,
        visibility=AuditVisibility.INTERNAL,
        after={
            "status": outbox.status.value,
            "event_type": outbox.event_type.value,
            "provider": outbox.provider.value,
            "internal_ticket_id": str(outbox.internal_ticket_id),
            "error": error,
        },
        request_ctx=ctx,
    )


def _update_link_status(
    db: Session,
    *,
    org_id: str,
    provider: HelpdeskProvider,
    internal_ticket_id: str,
    status: HelpdeskTicketLinkStatus,
    external_ticket_id: str | None = None,
    external_url: str | None = None,
) -> HelpdeskTicketLink:
    link = (
        db.query(HelpdeskTicketLink)
        .filter(HelpdeskTicketLink.provider == provider)
        .filter(HelpdeskTicketLink.internal_ticket_id == internal_ticket_id)
        .one_or_none()
    )
    if link is None:
        link = HelpdeskTicketLink(
            org_id=org_id,
            provider=provider,
            internal_ticket_id=internal_ticket_id,
            status=status,
            external_ticket_id=external_ticket_id,
            external_url=external_url,
            last_sync_at=_now(),
        )
        db.add(link)
    else:
        link.status = status
        link.external_ticket_id = external_ticket_id or link.external_ticket_id
        link.external_url = external_url or link.external_url
        link.last_sync_at = _now()
    return link


def enqueue_helpdesk_event(
    db: Session,
    *,
    org_id: str,
    provider: HelpdeskProvider,
    internal_ticket_id: str,
    event_type: HelpdeskOutboxEventType,
    payload: dict[str, Any],
    idempotency_key: str,
) -> HelpdeskOutbox:
    existing = db.query(HelpdeskOutbox).filter(HelpdeskOutbox.idempotency_key == idempotency_key).one_or_none()
    if existing:
        if existing.status == HelpdeskOutboxStatus.FAILED:
            existing.status = HelpdeskOutboxStatus.QUEUED
            existing.next_retry_at = _now()
        return existing

    outbox = HelpdeskOutbox(
        org_id=org_id,
        provider=provider,
        internal_ticket_id=internal_ticket_id,
        event_type=event_type,
        payload_json=payload,
        idempotency_key=idempotency_key,
        status=HelpdeskOutboxStatus.QUEUED,
        attempts_count=0,
        next_retry_at=_now(),
    )
    db.add(outbox)
    return outbox


def schedule_helpdesk_outbox(outbox: HelpdeskOutbox) -> None:
    celery_client.send_task("helpdesk.process_outbox", args=[str(outbox.id)])


def build_ticket_payload(
    *,
    ticket: SupportTicket,
    created_by_email: str | None,
    attachments: list[SupportTicketAttachment],
) -> dict[str, Any]:
    portal_url = build_portal_url(f"/client/support/{ticket.id}")
    return {
        "subject": ticket.subject,
        "description": ticket.message,
        "priority": ticket.priority.value,
        "internal_ticket_id": str(ticket.id),
        "org_id": str(ticket.org_id),
        "created_by_email": created_by_email,
        "portal_url": portal_url,
        "attachments": [
            {
                "file_name": attachment.file_name,
                "download_url": build_portal_url(f"/client/support/attachments/{attachment.id}/download"),
            }
            for attachment in attachments
        ],
    }


def build_comment_payload(
    *,
    ticket: SupportTicket,
    comment: SupportTicketComment,
    author_email: str | None,
) -> dict[str, Any]:
    portal_url = build_portal_url(f"/client/support/{ticket.id}")
    return {
        "message": comment.message,
        "author_email": author_email,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "portal_url": portal_url,
    }


def build_close_payload(*, ticket: SupportTicket) -> dict[str, Any]:
    return {
        "internal_ticket_id": str(ticket.id),
        "closed_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
    }


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _normalize_author_role(role: Any) -> str | None:
    if role is None:
        return None
    normalized = str(role).strip().lower().replace("-", "_")
    if normalized in {"enduser", "end_user"}:
        return "end_user"
    if normalized in {"agent", "admin"}:
        return "agent"
    return normalized or None


def normalize_zendesk_payload(payload: dict[str, Any], *, event_id: str) -> NormalizedHelpdeskEvent | None:
    ticket = payload.get("ticket") or {}
    external_ticket_id = (
        _normalize_text(payload.get("ticket_id"))
        or _normalize_text(ticket.get("id"))
        or _normalize_text(payload.get("id"))
    )
    if not external_ticket_id:
        return None

    event_type = _normalize_text(payload.get("event_type"))
    comment_payload = payload.get("comment") or {}
    if not event_type:
        if comment_payload or comment_payload.get("body"):
            event_type = "comment_created"
        elif payload.get("status") or ticket.get("status") or ticket.get("previous_status"):
            event_type = "status_changed"

    if event_type not in {"comment_created", "status_changed"}:
        return None

    author_payload = (
        comment_payload.get("author")
        or payload.get("author")
        or payload.get("current_user")
        or payload.get("assignee")
        or {}
    )
    author = HelpdeskAuthor(
        name=_normalize_text(author_payload.get("name")),
        email=_normalize_text(author_payload.get("email")),
        role=_normalize_author_role(author_payload.get("role")),
    )

    comment = None
    if event_type == "comment_created":
        body = _normalize_text(comment_payload.get("body") or comment_payload.get("text") or payload.get("comment"))
        if not body:
            return None
        comment = HelpdeskComment(
            body=body,
            is_public=bool(comment_payload.get("public")) if "public" in comment_payload else None,
            created_at=_normalize_text(comment_payload.get("created_at")),
        )

    status_change = None
    if event_type == "status_changed":
        status_change = HelpdeskStatusChange(
            from_status=_normalize_text(ticket.get("previous_status") or payload.get("previous_status")),
            to_status=_normalize_text(payload.get("status") or ticket.get("status")),
        )

    return NormalizedHelpdeskEvent(
        event_id=event_id,
        event_type=event_type,
        external_ticket_id=str(external_ticket_id),
        author=author,
        comment=comment,
        status=status_change,
    )


def map_zendesk_status_to_support(status: str | None) -> SupportTicketStatus | None:
    if not status:
        return None
    normalized = status.strip().lower()
    if normalized in {"new", "open"}:
        return SupportTicketStatus.OPEN
    if normalized in {"pending", "hold"}:
        return SupportTicketStatus.IN_PROGRESS
    if normalized in {"solved", "closed"}:
        return SupportTicketStatus.CLOSED
    return None


def apply_helpdesk_inbound_event(
    db: Session,
    *,
    event: NormalizedHelpdeskEvent,
    provider: HelpdeskProvider,
) -> tuple[HelpdeskInboundEventStatus, str | None, str | None]:
    link = (
        db.query(HelpdeskTicketLink)
        .filter(HelpdeskTicketLink.provider == provider)
        .filter(HelpdeskTicketLink.external_ticket_id == event.external_ticket_id)
        .one_or_none()
    )
    if not link:
        return HelpdeskInboundEventStatus.IGNORED, "unknown_external_ticket", None
    ticket = db.query(SupportTicket).filter(SupportTicket.id == str(link.internal_ticket_id)).one_or_none()
    if not ticket:
        return HelpdeskInboundEventStatus.IGNORED, "missing_internal_ticket", None

    audit_service = AuditService(db)
    request_ctx = RequestContext(actor_type=ActorType.SERVICE, actor_id=HELPDESK_INBOUND_ACTOR_ID)

    if event.event_type == "comment_created":
        role = event.author.role if event.author else None
        if role == "end_user":
            return HelpdeskInboundEventStatus.IGNORED, "end_user_comment", str(ticket.id)
        if not event.comment or not event.comment.body:
            return HelpdeskInboundEventStatus.IGNORED, "empty_comment", str(ticket.id)
        comment = SupportTicketComment(
            ticket_id=str(ticket.id),
            user_id=HELPDESK_INBOUND_ACTOR_ID,
            message=event.comment.body,
            source=HELPDESK_INBOUND_SOURCE,
        )
        ticket.updated_at = _now()
        mark_first_response(ticket, audit=audit_service, request_ctx=request_ctx)
        db.add(comment)
        db.add(ticket)
        db.flush()
        audit_service.audit(
            event_type="helpdesk_inbound_comment_applied",
            entity_type="support_ticket",
            entity_id=str(ticket.id),
            action="helpdesk_inbound_comment_applied",
            visibility=AuditVisibility.INTERNAL,
            after={"comment_id": str(comment.id)},
            request_ctx=request_ctx,
        )
        return HelpdeskInboundEventStatus.PROCESSED, None, str(ticket.id)

    if event.event_type == "status_changed":
        mapped_status = map_zendesk_status_to_support(event.status.to_status if event.status else None)
        if not mapped_status:
            return HelpdeskInboundEventStatus.IGNORED, "unsupported_status", str(ticket.id)
        if ticket.status == SupportTicketStatus.CLOSED and mapped_status == SupportTicketStatus.OPEN:
            return HelpdeskInboundEventStatus.IGNORED, "reopen_ignored", str(ticket.id)
        if ticket.status == mapped_status:
            return HelpdeskInboundEventStatus.PROCESSED, None, str(ticket.id)
        previous = ticket.status
        ticket.status = mapped_status
        ticket.last_changed_by = HELPDESK_INBOUND_SOURCE
        ticket.updated_at = _now()
        if mapped_status == SupportTicketStatus.CLOSED:
            mark_resolution(ticket, audit=audit_service, request_ctx=request_ctx)
        db.add(ticket)
        db.flush()
        audit_service.audit(
            event_type="helpdesk_inbound_status_applied",
            entity_type="support_ticket",
            entity_id=str(ticket.id),
            action="helpdesk_inbound_status_applied",
            visibility=AuditVisibility.INTERNAL,
            after={"from": previous.value, "to": ticket.status.value},
            request_ctx=request_ctx,
        )
        return HelpdeskInboundEventStatus.PROCESSED, None, str(ticket.id)

    return HelpdeskInboundEventStatus.IGNORED, "unsupported_event", str(ticket.id)


def build_idempotency(event_type: str, org_id: str, entity_id: str, job_id: str | None = None) -> str:
    return build_idempotency_key(event_type, org_id, entity_id, job_id)


def deliver_helpdesk_outbox(db: Session, *, outbox: HelpdeskOutbox) -> tuple[HelpdeskOutboxStatus, int | None]:
    if outbox.status == HelpdeskOutboxStatus.SENT:
        return HelpdeskOutboxStatus.SENT, None
    if outbox.attempts_count >= MAX_ATTEMPTS:
        outbox.status = HelpdeskOutboxStatus.FAILED
        outbox.last_error = outbox.last_error or "max_attempts_reached"
        outbox.next_retry_at = None
        _audit_outbox_event(db, event_type="helpdesk_sync_failed", outbox=outbox, error=outbox.last_error)
        return outbox.status, None

    integration = get_active_integration(db, org_id=str(outbox.org_id))
    if not integration:
        outbox.status = HelpdeskOutboxStatus.FAILED
        outbox.last_error = "integration_disabled"
        outbox.next_retry_at = None
        _audit_outbox_event(db, event_type="helpdesk_sync_failed", outbox=outbox, error=outbox.last_error)
        return outbox.status, None
    if integration.provider != outbox.provider:
        outbox.status = HelpdeskOutboxStatus.FAILED
        outbox.last_error = "provider_mismatch"
        outbox.next_retry_at = None
        _audit_outbox_event(db, event_type="helpdesk_sync_failed", outbox=outbox, error=outbox.last_error)
        return outbox.status, None

    outbox.attempts_count += 1
    try:
        provider = _provider_from_integration(integration)
        if outbox.event_type == HelpdeskOutboxEventType.TICKET_CREATED:
            payload = dict(outbox.payload_json or {})
            payload["description"] = _format_ticket_description(payload)
            payload["requester_email"] = payload.get("created_by_email")
            payload["tags"] = [
                f"org_id:{payload.get('org_id')}",
                f"internal_ticket_id:{payload.get('internal_ticket_id')}",
            ]
            ref = provider.create_ticket(payload)
            _update_link_status(
                db,
                org_id=str(outbox.org_id),
                provider=outbox.provider,
                internal_ticket_id=str(outbox.internal_ticket_id),
                status=HelpdeskTicketLinkStatus.LINKED,
                external_ticket_id=ref.external_ticket_id,
                external_url=ref.external_url,
            )
        elif outbox.event_type == HelpdeskOutboxEventType.COMMENT_ADDED:
            link = (
                db.query(HelpdeskTicketLink)
                .filter(HelpdeskTicketLink.provider == outbox.provider)
                .filter(HelpdeskTicketLink.internal_ticket_id == str(outbox.internal_ticket_id))
                .one_or_none()
            )
            if not link or not link.external_ticket_id:
                raise HelpdeskProviderError("ticket_link_missing", retryable=True)
            payload = dict(outbox.payload_json or {})
            payload["comment"] = _format_comment(payload)
            provider.add_comment(link.external_ticket_id, payload)
            link.last_sync_at = _now()
            link.status = HelpdeskTicketLinkStatus.LINKED
        elif outbox.event_type == HelpdeskOutboxEventType.TICKET_CLOSED:
            link = (
                db.query(HelpdeskTicketLink)
                .filter(HelpdeskTicketLink.provider == outbox.provider)
                .filter(HelpdeskTicketLink.internal_ticket_id == str(outbox.internal_ticket_id))
                .one_or_none()
            )
            if not link or not link.external_ticket_id:
                raise HelpdeskProviderError("ticket_link_missing", retryable=True)
            provider.close_ticket(link.external_ticket_id)
            link.last_sync_at = _now()
            link.status = HelpdeskTicketLinkStatus.LINKED
        else:
            raise HelpdeskProviderError("unsupported_event", retryable=False)

        outbox.status = HelpdeskOutboxStatus.SENT
        outbox.sent_at = _now()
        outbox.last_error = None
        outbox.next_retry_at = None
        _audit_outbox_event(db, event_type="helpdesk_sync_succeeded", outbox=outbox)
        return outbox.status, None
    except HelpdeskProviderError as exc:
        outbox.last_error = str(exc)
        retry_delay = _next_retry_delay(outbox.attempts_count) if exc.retryable else None
        if retry_delay and outbox.attempts_count < MAX_ATTEMPTS:
            outbox.status = HelpdeskOutboxStatus.QUEUED
            outbox.next_retry_at = _now() + timedelta(seconds=retry_delay)
            _audit_outbox_event(db, event_type="helpdesk_sync_failed", outbox=outbox, error=outbox.last_error)
            logger.warning(
                "helpdesk_outbox.retry_scheduled",
                extra={
                    "outbox_id": str(outbox.id),
                    "org_id": outbox.org_id,
                    "event_type": outbox.event_type.value,
                    "error": outbox.last_error,
                },
            )
            return HelpdeskOutboxStatus.FAILED, retry_delay
        outbox.status = HelpdeskOutboxStatus.FAILED
        outbox.next_retry_at = None
        _audit_outbox_event(db, event_type="helpdesk_sync_failed", outbox=outbox, error=outbox.last_error)
        _update_link_status(
            db,
            org_id=str(outbox.org_id),
            provider=outbox.provider,
            internal_ticket_id=str(outbox.internal_ticket_id),
            status=HelpdeskTicketLinkStatus.FAILED,
        )
        _maybe_notify_sync_failed(db, org_id=str(outbox.org_id), outbox=outbox)
        logger.warning(
            "helpdesk_outbox.failed",
            extra={
                "outbox_id": str(outbox.id),
                "org_id": outbox.org_id,
                "event_type": outbox.event_type.value,
                "error": outbox.last_error,
            },
        )
        return outbox.status, None


def _maybe_notify_sync_failed(db: Session, *, org_id: str, outbox: HelpdeskOutbox) -> None:
    recent_failures = (
        db.query(HelpdeskOutbox)
        .filter(HelpdeskOutbox.org_id == org_id)
        .filter(HelpdeskOutbox.status == HelpdeskOutboxStatus.FAILED)
        .order_by(HelpdeskOutbox.created_at.desc())
        .limit(FAILURE_NOTIFICATION_THRESHOLD)
        .all()
    )
    if len(recent_failures) < FAILURE_NOTIFICATION_THRESHOLD:
        return
    create_notification(
        db,
        org_id=org_id,
        event_type="helpdesk_sync_failed",
        severity=ClientNotificationSeverity.WARNING,
        title="Helpdesk sync failed",
        body="Синхронизация helpdesk временно недоступна. Мы продолжаем попытки отправки.",
        link="/client/support",
        target_roles=ADMIN_TARGET_ROLES,
        entity_type="helpdesk_outbox",
        entity_id=str(outbox.id),
    )


def get_integration_last_error(db: Session, *, org_id: str) -> str | None:
    outbox = (
        db.query(HelpdeskOutbox)
        .filter(HelpdeskOutbox.org_id == org_id)
        .filter(HelpdeskOutbox.status == HelpdeskOutboxStatus.FAILED)
        .order_by(HelpdeskOutbox.created_at.desc())
        .first()
    )
    if outbox:
        return outbox.last_error
    return None


def build_idempotency_for_ticket(event_type: HelpdeskOutboxEventType, ticket_id: str, org_id: str) -> str:
    return build_idempotency_key(event_type.value, org_id, ticket_id)


def build_idempotency_for_comment(
    event_type: HelpdeskOutboxEventType,
    ticket_id: str,
    org_id: str,
    comment_id: str,
) -> str:
    return build_idempotency_key(event_type.value, org_id, ticket_id, comment_id)


def build_idempotency_for_close(event_type: HelpdeskOutboxEventType, ticket_id: str, org_id: str) -> str:
    return build_idempotency_key(event_type.value, org_id, ticket_id)


def integration_payload_from_config(config: dict[str, Any]) -> dict[str, Any]:
    return _safe_config_values(config)


__all__ = [
    "HELPDESK_INBOUND_ACTOR_ID",
    "HELPDESK_INBOUND_SOURCE",
    "HelpdeskProviderError",
    "HelpdeskProvider",
    "ExternalTicketRef",
    "NormalizedHelpdeskEvent",
    "apply_helpdesk_inbound_event",
    "build_close_payload",
    "build_comment_payload",
    "build_idempotency",
    "build_idempotency_for_close",
    "build_idempotency_for_comment",
    "build_idempotency_for_ticket",
    "build_ticket_payload",
    "deliver_helpdesk_outbox",
    "enqueue_helpdesk_event",
    "get_active_integration",
    "get_integration",
    "get_integration_last_error",
    "integration_payload_from_config",
    "map_zendesk_status_to_support",
    "normalize_zendesk_payload",
    "schedule_helpdesk_outbox",
    "upsert_integration",
]
