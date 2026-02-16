from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.domains.documents.models import Document, DocumentTimelineEvent


class TimelineEventType:
    DOCUMENT_CREATED = "DOCUMENT_CREATED"
    FILE_UPLOADED = "FILE_UPLOADED"
    STATUS_CHANGED = "STATUS_CHANGED"


class TimelineActorType:
    USER = "USER"
    SYSTEM = "SYSTEM"


@dataclass(slots=True)
class TimelineRequestContext:
    ip: str | None = None
    user_agent: str | None = None


class DocumentTimelineService:
    def __init__(self, repo):
        self.repo = repo

    def append_event(
        self,
        document: Document,
        *,
        event_type: str,
        message: str | None = None,
        meta: dict | None = None,
        actor_type: str = TimelineActorType.SYSTEM,
        actor_user_id: str | None = None,
        request_context: TimelineRequestContext | None = None,
    ) -> DocumentTimelineEvent:
        return self.repo.create_timeline_event(
            id=str(uuid4()),
            document_id=str(document.id),
            client_id=document.client_id,
            event_type=event_type,
            message=message,
            meta=meta or {},
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            ip=request_context.ip if request_context else None,
            user_agent=request_context.user_agent if request_context else None,
        )
