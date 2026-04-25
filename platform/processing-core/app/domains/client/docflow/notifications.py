from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.domains.client.docflow.models import ClientDocflowNotification


@dataclass(slots=True)
class ClientDocflowNotificationsService:
    db: Session

    def create(
        self,
        *,
        client_id: str,
        user_id: str | None,
        title: str,
        message: str | None = None,
        kind: str | None = None,
        payload: dict | None = None,
        severity: str = "INFO",
        dedupe_key: str | None = None,
        body: str | None = None,
        event_type: str | None = None,
        meta_json: dict | None = None,
    ) -> ClientDocflowNotification:
        resolved_message = message or body or ""
        resolved_kind = kind or event_type or "INFO"
        resolved_payload = payload if payload is not None else (meta_json or {})
        item = ClientDocflowNotification(
            id=new_uuid_str(),
            client_id=client_id,
            user_id=user_id,
            channel="in_app",
            title=title,
            body=resolved_message,
            event_type=resolved_kind,
            meta_json=resolved_payload,
            message=resolved_message,
            kind=resolved_kind,
            payload=resolved_payload,
            severity=severity,
            dedupe_key=dedupe_key,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_for_client(self, *, client_id: str, user_id: str | None, limit: int) -> list[ClientDocflowNotification]:
        stmt = select(ClientDocflowNotification).where(ClientDocflowNotification.client_id == client_id)
        if user_id:
            stmt = stmt.where((ClientDocflowNotification.user_id.is_(None)) | (ClientDocflowNotification.user_id == user_id))
        stmt = stmt.order_by(ClientDocflowNotification.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def unread_count(self, *, client_id: str, user_id: str | None) -> int:
        stmt = select(func.count(ClientDocflowNotification.id)).where(
            ClientDocflowNotification.client_id == client_id,
            ClientDocflowNotification.is_read.is_(False),
        )
        if user_id:
            stmt = stmt.where((ClientDocflowNotification.user_id.is_(None)) | (ClientDocflowNotification.user_id == user_id))
        return int(self.db.execute(stmt).scalar_one())

    def mark_read(self, *, notification_id: str, client_id: str, user_id: str | None) -> ClientDocflowNotification | None:
        stmt = select(ClientDocflowNotification).where(
            ClientDocflowNotification.id == notification_id,
            ClientDocflowNotification.client_id == client_id,
        )
        if user_id:
            stmt = stmt.where((ClientDocflowNotification.user_id.is_(None)) | (ClientDocflowNotification.user_id == user_id))
        item = self.db.execute(stmt).scalar_one_or_none()
        if item is None:
            return None
        if not item.is_read:
            item.is_read = True
            item.read_at = datetime.now(timezone.utc)
            self.db.add(item)
            self.db.commit()
            self.db.refresh(item)
        return item
