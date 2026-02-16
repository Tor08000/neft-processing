from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TimelineEventOut(BaseModel):
    id: str
    event_type: str
    message: str | None = None
    meta: dict
    actor_type: str
    actor_user_id: str | None = None
    created_at: datetime
