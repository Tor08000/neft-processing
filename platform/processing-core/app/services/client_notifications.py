from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import MetaData, Table, and_, desc, inspect, or_, select
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
    "billing_due_soon_7d": "billing_due_soon_7d",
    "billing_due_soon_1d": "billing_due_soon_1d",
    "billing_overdue_1d": "billing_overdue_1d",
    "billing_overdue_7d": "billing_overdue_7d",
    "billing_pre_suspend_1d": "billing_pre_suspend_1d",
    "billing_suspended": "billing_suspended",
}


def normalize_roles(token: dict) -> list[str]:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if token.get("role"):
        roles.append(token["role"])
    return [str(role).upper() for role in roles]


def _table_exists(db: Session, name: str) -> bool:
    try:
        return inspect(db.get_bind()).has_table(name)
    except Exception:
        return False


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind())


def _column(table: Table, name: str):
    return table.c.get(name)


def _normalize_client_uuid(value: object | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        return str(UUID(str(value).strip()))
    except (TypeError, ValueError, AttributeError):
        return None


def _resolve_client_scope_id_from_orgs(db: Session, *, org_id: int) -> str | None:
    if not _table_exists(db, "orgs"):
        return None
    try:
        orgs = _table(db, "orgs")
    except Exception:
        return None

    id_col = _column(orgs, "id")
    client_col = _column(orgs, "client_id") or _column(orgs, "client_uuid")
    if id_col is None or client_col is None:
        return None

    try:
        record = db.execute(select(client_col).where(id_col == org_id)).scalar_one_or_none()
    except Exception:
        return None
    return _normalize_client_uuid(record)


def _resolve_client_scope_id_from_subscriptions(db: Session, *, org_id: int) -> str | None:
    if not _table_exists(db, "client_subscriptions"):
        return None
    try:
        client_subscriptions = _table(db, "client_subscriptions")
    except Exception:
        return None

    tenant_col = _column(client_subscriptions, "tenant_id")
    client_col = _column(client_subscriptions, "client_id")
    if tenant_col is None or client_col is None:
        return None

    query = select(client_col).where(tenant_col == org_id)
    created_at_col = _column(client_subscriptions, "created_at")
    start_at_col = _column(client_subscriptions, "start_at")
    if created_at_col is not None:
        query = query.order_by(desc(created_at_col))
    elif start_at_col is not None:
        query = query.order_by(desc(start_at_col))
    query = query.limit(1)

    try:
        record = db.execute(query).scalar_one_or_none()
    except Exception:
        return None
    return _normalize_client_uuid(record)


def resolve_client_scope_id(db: Session, org_id: str | None, *, client_id: str | None = None) -> str | None:
    resolved_client_id = _normalize_client_uuid(client_id)
    if resolved_client_id is not None:
        return resolved_client_id

    candidate = str(org_id).strip() if org_id not in (None, "") else ""
    if not candidate:
        return None

    direct_uuid = _normalize_client_uuid(candidate)
    if direct_uuid is not None:
        return direct_uuid

    try:
        record = db.query(Client.id).filter(Client.external_id == candidate).scalar()
    except Exception:
        record = None
    resolved_client_id = _normalize_client_uuid(record)
    if resolved_client_id is not None:
        return resolved_client_id

    if not candidate.isdigit():
        return None

    org_id_int = int(candidate)
    return _resolve_client_scope_id_from_orgs(db, org_id=org_id_int) or _resolve_client_scope_id_from_subscriptions(
        db,
        org_id=org_id_int,
    )


def resolve_client_email(db: Session, org_id: str, *, client_id: str | None = None) -> str | None:
    resolved_client_id = resolve_client_scope_id(db, org_id, client_id=client_id)
    if not resolved_client_id:
        return None
    email = db.query(Client.email).filter(Client.id == UUID(resolved_client_id)).scalar()
    return str(email) if email else None


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
) -> ClientNotification | None:
    resolved_notification_org_id = resolve_client_scope_id(db, org_id)
    if not resolved_notification_org_id:
        logger.warning(
            "client_notification_scope_unresolved",
            extra={"org_id": org_id, "event_type": event_type, "entity_type": entity_type, "entity_id": entity_id},
        )
        if email_to:
            send_notification_email(
                db=db,
                to_email=email_to,
                title=title,
                body=body,
                link=link,
                event_type=event_type,
                org_id=str(org_id),
                notification_id=None,
                entity_id=entity_id,
                idempotency_key=email_idempotency_key,
                context=email_context,
            )
        return None

    notification = ClientNotification(
        org_id=resolved_notification_org_id,
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
    "resolve_client_scope_id",
]
