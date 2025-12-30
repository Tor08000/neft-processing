from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.support_request import (
    SupportRequestPriority,
    SupportRequestScopeType,
    SupportRequestStatus,
    SupportRequestSubjectType,
)


class SupportRequestCreate(BaseModel):
    scope_type: SupportRequestScopeType
    subject_type: SupportRequestSubjectType
    subject_id: str | None = None
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    correlation_id: str | None = None
    event_id: str | None = None


class SupportRequestStatusChange(BaseModel):
    status: SupportRequestStatus


class SupportRequestTimelineEvent(BaseModel):
    status: SupportRequestStatus
    occurred_at: datetime


class SupportRequestOut(BaseModel):
    id: str
    tenant_id: int
    client_id: str | None
    partner_id: str | None
    created_by_user_id: str | None
    scope_type: SupportRequestScopeType
    subject_type: SupportRequestSubjectType
    subject_id: str | None
    correlation_id: str | None
    event_id: str | None
    title: str
    description: str
    status: SupportRequestStatus
    priority: SupportRequestPriority
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class SupportRequestDetail(SupportRequestOut):
    timeline: list[SupportRequestTimelineEvent] = Field(default_factory=list)


class SupportRequestListResponse(BaseModel):
    items: list[SupportRequestOut]
    total: int
    limit: int
    offset: int


__all__ = [
    "SupportRequestCreate",
    "SupportRequestDetail",
    "SupportRequestListResponse",
    "SupportRequestOut",
    "SupportRequestStatusChange",
    "SupportRequestTimelineEvent",
]
