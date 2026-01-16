from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.models.client_notification import ClientNotification
from app.schemas.client_notifications import (
    ClientNotificationListResponse,
    ClientNotificationOut,
    ClientNotificationUnreadCount,
)
from app.services.client_notifications import normalize_roles

router = APIRouter(prefix="/client/notifications", tags=["client-notifications"])


def _resolve_org_id(token: dict) -> str:
    org_id = token.get("client_id") or token.get("org_id")
    if not org_id:
        raise HTTPException(status_code=403, detail="missing_org")
    return str(org_id)


def _resolve_user_id(token: dict) -> str:
    user_id = str(token.get("user_id") or token.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=403, detail="missing_user")
    return user_id


def _build_cursor(notification: ClientNotification) -> str:
    return f"{notification.created_at.isoformat()}|{notification.id}"


def _parse_cursor(cursor: str) -> tuple[datetime, str]:
    parts = cursor.split("|", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="invalid_cursor")
    try:
        created_at = datetime.fromisoformat(parts[0])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_cursor") from exc
    return created_at, parts[1]


def _has_access(notification: ClientNotification, *, user_id: str, roles: Iterable[str]) -> bool:
    if notification.target_user_id and notification.target_user_id == user_id:
        return True
    target_roles = [role.upper() for role in (notification.target_roles or [])]
    role_set = {role.upper() for role in roles}
    return bool(target_roles and role_set.intersection(target_roles))


def _serialize(notification: ClientNotification) -> ClientNotificationOut:
    return ClientNotificationOut(
        id=str(notification.id),
        type=notification.type,
        severity=notification.severity,
        title=notification.title,
        body=notification.body,
        link=notification.link,
        entity_type=notification.entity_type,
        entity_id=notification.entity_id,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


@router.get("", response_model=ClientNotificationListResponse)
def list_notifications(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    unread_only: bool = Query(False, alias="unread_only"),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = None,
) -> ClientNotificationListResponse:
    org_id = _resolve_org_id(token)
    user_id = _resolve_user_id(token)
    roles = normalize_roles(token)

    dialect_name = db.get_bind().dialect.name
    allow_role_overlap = dialect_name != "sqlite"

    filters = [ClientNotification.org_id == org_id]
    if unread_only:
        filters.append(ClientNotification.read_at.is_(None))
    if cursor:
        created_at, cursor_id = _parse_cursor(cursor)
        filters.append(
            or_(
                ClientNotification.created_at < created_at,
                and_(ClientNotification.created_at == created_at, ClientNotification.id < cursor_id),
            )
        )
    if allow_role_overlap:
        scope_filter = or_(
            ClientNotification.target_user_id == user_id,
            ClientNotification.target_roles.overlap(roles) if roles else False,
        )
        filters.append(scope_filter)

    fetch_limit = limit + 1 if allow_role_overlap else min(limit + 50, 200)
    query = (
        db.query(ClientNotification)
        .filter(and_(*filters))
        .order_by(ClientNotification.created_at.desc(), ClientNotification.id.desc())
        .limit(fetch_limit)
    )
    rows = query.all()

    if not allow_role_overlap:
        rows = [row for row in rows if _has_access(row, user_id=user_id, roles=roles)]

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = _build_cursor(rows[-1])

    return ClientNotificationListResponse(items=[_serialize(row) for row in rows], next_cursor=next_cursor)


@router.post("/{notification_id}/read", response_model=ClientNotificationOut)
def mark_notification_read(
    notification_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientNotificationOut:
    org_id = _resolve_org_id(token)
    user_id = _resolve_user_id(token)
    roles = normalize_roles(token)

    notification = (
        db.query(ClientNotification)
        .filter(ClientNotification.id == notification_id, ClientNotification.org_id == org_id)
        .one_or_none()
    )
    if not notification or not _has_access(notification, user_id=user_id, roles=roles):
        raise HTTPException(status_code=404, detail="notification_not_found")

    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.add(notification)
        db.commit()
        db.refresh(notification)

    return _serialize(notification)


@router.post("/read-all")
def mark_all_notifications_read(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    unread_only: bool = Query(True, alias="unread_only"),
) -> dict:
    org_id = _resolve_org_id(token)
    user_id = _resolve_user_id(token)
    roles = normalize_roles(token)

    now = datetime.now(timezone.utc)
    query = db.query(ClientNotification).filter(ClientNotification.org_id == org_id)
    if unread_only:
        query = query.filter(ClientNotification.read_at.is_(None))

    notifications = query.all()
    updated = 0
    for notification in notifications:
        if not _has_access(notification, user_id=user_id, roles=roles):
            continue
        if notification.read_at is None:
            notification.read_at = now
            updated += 1
            db.add(notification)

    db.commit()
    return {"updated": updated}


@router.get("/unread-count", response_model=ClientNotificationUnreadCount)
def unread_count(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientNotificationUnreadCount:
    org_id = _resolve_org_id(token)
    user_id = _resolve_user_id(token)
    roles = normalize_roles(token)

    dialect_name = db.get_bind().dialect.name
    allow_role_overlap = dialect_name != "sqlite"
    query = db.query(ClientNotification).filter(
        ClientNotification.org_id == org_id,
        ClientNotification.read_at.is_(None),
    )
    if allow_role_overlap:
        query = query.filter(
            or_(
                ClientNotification.target_user_id == user_id,
                ClientNotification.target_roles.overlap(roles) if roles else False,
            )
        )
        count = query.count()
    else:
        rows = query.all()
        count = len([row for row in rows if _has_access(row, user_id=user_id, roles=roles)])

    return ClientNotificationUnreadCount(count=count)
