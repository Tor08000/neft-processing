from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.client.signing.models import ClientAuditEvent


@dataclass(slots=True)
class ClientDocflowTimelineService:
    db: Session

    def list_events(
        self,
        *,
        application_id: str | None,
        doc_id: str | None,
        client_id: str | None,
        limit: int,
    ) -> list[ClientAuditEvent]:
        stmt = select(ClientAuditEvent)
        if application_id:
            stmt = stmt.where(ClientAuditEvent.application_id == application_id)
        if doc_id:
            stmt = stmt.where(ClientAuditEvent.doc_id == doc_id)
        if client_id:
            stmt = stmt.where(ClientAuditEvent.client_id == client_id)
        stmt = stmt.order_by(ClientAuditEvent.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
