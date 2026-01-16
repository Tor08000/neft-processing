from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_notification import ClientNotification, ClientNotificationSeverity
from app.services.notifications.email_sender import ConsoleEmailSender, EmailSender, SmtpEmailSender

logger = logging.getLogger(__name__)

ADMIN_TARGET_ROLES = ["CLIENT_OWNER", "CLIENT_ADMIN"]


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


def _pick_email_sender() -> EmailSender:
    smtp_sender = SmtpEmailSender()
    if smtp_sender.host:
        return smtp_sender
    return ConsoleEmailSender()


def send_notification_email(*, to_email: str, title: str, body: str, link: str | None) -> str | None:
    sender = _pick_email_sender()
    message = body
    if link:
        message = f"{body}\n\nОткрыть: {link}"
    try:
        return sender.send(to=to_email, subject=title, html=None, text=message)
    except Exception:  # noqa: BLE001 - log and continue
        logger.exception("client_notification_email_failed", extra={"email": to_email, "title": title})
        return None


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

    if email_to:
        message_id = send_notification_email(to_email=email_to, title=title, body=body, link=link)
        if message_id is not None:
            notification.delivered_email_at = datetime.now(timezone.utc)
            db.add(notification)
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
