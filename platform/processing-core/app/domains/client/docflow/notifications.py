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
        body: str,
        event_type: str,
        meta_json: dict | None = None,
        channel: str = "IN_APP",
    ) -> ClientDocflowNotification:
        item = ClientDocflowNotification(
            id=new_uuid_str(),
            client_id=client_id,
            user_id=user_id,
            title=title,
            body=body,
            event_type=event_type,
            channel=channel,
            meta_json=meta_json or {},
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
            ClientDocflowNotification.read_at.is_(None),
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
        if item.read_at is None:
            item.read_at = datetime.now(timezone.utc)
            self.db.add(item)
            self.db.commit()
            self.db.refresh(item)
        return item
