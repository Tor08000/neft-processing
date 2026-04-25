from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.bi import BiSyncRunStatus, BiSyncRunType


class BiSyncRunOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    type: BiSyncRunType
    status: BiSyncRunStatus
    rows_written: int | None
    started_at: datetime
    finished_at: datetime | None
    error: str | None
