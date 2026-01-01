from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.cases import CaseCommentType, CaseKind, CasePriority, CaseStatus


class CaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CaseKind
    entity_id: str | None = None
    kpi_key: str | None = None
    window_days: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, max_length=160)
    priority: CasePriority = CasePriority.MEDIUM
    note: str | None = None
    explain: dict[str, Any] | None = None
    diff: dict[str, Any] | None = None
    selected_actions: list[dict[str, Any]] | None = None


class CaseUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CaseStatus | None = None
    assigned_to: str | None = None
    priority: CasePriority | None = None


class CaseCommentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1)


class CaseSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    explain_snapshot: dict[str, Any]
    diff_snapshot: dict[str, Any] | None
    selected_actions: list[dict[str, Any]] | None
    note: str | None
    created_at: datetime


class CaseCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    author: str | None
    type: CaseCommentType
    body: str
    created_at: datetime


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: int
    kind: CaseKind
    entity_id: str | None
    kpi_key: str | None
    window_days: int | None
    title: str
    status: CaseStatus
    priority: CasePriority
    created_by: str | None
    assigned_to: str | None
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


class CaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CaseResponse]
    total: int
    limit: int
    next_cursor: str | None = None


class CaseDetailsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case: CaseResponse
    latest_snapshot: CaseSnapshotOut | None
    comments: list[CaseCommentOut]
    snapshots: list[CaseSnapshotOut] | None = None


__all__ = [
    "CaseCommentCreateRequest",
    "CaseCommentOut",
    "CaseCreateRequest",
    "CaseDetailsResponse",
    "CaseListResponse",
    "CaseResponse",
    "CaseSnapshotOut",
    "CaseUpdateRequest",
]
