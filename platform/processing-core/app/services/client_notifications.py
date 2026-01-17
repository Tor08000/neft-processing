from __future__ import annotations

import logging

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_notification import ClientNotification, ClientNotificationSeverity
from app.services.email_service import build_idempotency_key, enqueue_templated_email
from app.services.email_templates import build_portal_url
from app.services.notification_metrics import metrics as notification_metrics

logger = logging.getLogger(__name__)

ADMIN_TARGET_ROLES = ["CLIENT_OWNER", "CLIENT_ADMIN"]

EMAIL_TEMPLATE_MAP = {
    "export_ready": "export_ready",
    "export_failed": "export_failed",
    "scheduled_report_ready": "scheduled_report_ready",
    "support_ticket_commented": "support_ticket_commented",
    "support_sla_first_response_breached": "support_sla_first_response_breached",
    "support_sla_resolution_breached": "support_sla_resolution_breached",
}


def normalize_roles(token: dict) -> list[str]:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if token.get("role"):
        roles.append(token["role"])
    return [str(role).upper() for role in roles]


def resolve_client_email(db: Session, org_id: str) -> str | None:
    client = db.query(Client).filter(Client.id == org_id).one_or_none()
    if client and client.email:
        return client.email
    return None


def send_notification_email(
    *,
    db: Session,
    to_email: str,
    title: str,
    body: str,
    link: str | None,
    event_type: str,
    org_id: str,
    notification_id: str | None,
    entity_id: str | None,
    idempotency_key: str | None = None,
    context: dict[str, str] | None = None,
) -> None:
    template_key = EMAIL_TEMPLATE_MAP.get(event_type)
    if not template_key:
        return
    resolved_entity_id = entity_id or notification_id
    if not resolved_entity_id:
        logger.warning("client_notification_email_missing_entity", extra={"event_type": event_type, "org_id": org_id})
        return
    resolved_key = idempotency_key or build_idempotency_key(event_type, org_id, resolved_entity_id)
    portal_link = build_portal_url(link)
    try:
        email_context = {"body": body, "link": portal_link, "title": title}
        if context:
            email_context.update(context)
        enqueue_templated_email(
            db,
            template_key=template_key,
            to=[to_email],
            idempotency_key=resolved_key,
            org_id=org_id,
            user_id=None,
            context=email_context,
            tags={"client_notification_id": notification_id} if notification_id else None,
        )
    except Exception:  # noqa: BLE001 - log and continue
        logger.exception(
            "client_notification_email_failed",
            extra={"email": to_email, "title": title, "event_type": event_type},
        )


def create_notification(
    db: Session,
    *,
    org_id: str,
    event_type: str,
    severity: ClientNotificationSeverity,
    title: str,
    body: str,
    link: str | None = None,
    target_user_id: str | None = None,
    target_roles: list[str] | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    meta_json: dict[str, object] | None = None,
    email_to: str | None = None,
    email_idempotency_key: str | None = None,
    email_context: dict[str, str] | None = None,
) -> ClientNotification:
    notification = ClientNotification(
        org_id=org_id,
        target_user_id=target_user_id,
        target_roles=target_roles or None,
        type=event_type,
        severity=severity,
        title=title,
        body=body,
        link=link,
        entity_type=entity_type,
        entity_id=entity_id,
        meta_json=meta_json,
    )
    db.add(notification)
    db.flush()
    notification_metrics.mark_created(event_type, severity.value)

    if email_to:
        send_notification_email(
            db=db,
            to_email=email_to,
            title=title,
            body=body,
            link=link,
            event_type=event_type,
            org_id=str(org_id),
            notification_id=str(notification.id),
            entity_id=entity_id,
            idempotency_key=email_idempotency_key,
            context=email_context,
        )
    return notification


def build_scope_filter(
    *,
    org_id: str,
    user_id: str,
    roles: list[str],
    allow_role_overlap: bool = True,
) -> list:
    base_filters: list = [ClientNotification.org_id == org_id]
    role_filter = None
    if roles and allow_role_overlap:
        role_filter = ClientNotification.target_roles.overlap(roles)
    if role_filter is not None:
        base_filters.append(or_(ClientNotification.target_user_id == user_id, role_filter))
    else:
        base_filters.append(ClientNotification.target_user_id == user_id)
    return base_filters


def ensure_access(
    db: Session,
    *,
    notification_id: str,
    org_id: str,
    user_id: str,
    roles: list[str],
    allow_role_overlap: bool = True,
) -> ClientNotification | None:
    filters = build_scope_filter(org_id=org_id, user_id=user_id, roles=roles, allow_role_overlap=allow_role_overlap)
    filters.append(ClientNotification.id == notification_id)
    return db.query(ClientNotification).filter(and_(*filters)).one_or_none()


__all__ = [
    "ADMIN_TARGET_ROLES",
    "ClientNotificationSeverity",
    "create_notification",
    "ensure_access",
    "normalize_roles",
    "resolve_client_email",
]
