from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.marketplace.services import ServiceCardOut, ServiceLocationOut, ServiceScheduleOut

class ModerationEntityType(str, Enum):
    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"
    OFFER = "OFFER"


class ModerationStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class ModerationAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SUSPEND = "SUSPEND"


class ModerationReasonCode(str, Enum):
    INVALID_CONTENT = "INVALID_CONTENT"
    MISSING_INFO = "MISSING_INFO"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    DUPLICATE = "DUPLICATE"
    WRONG_CATEGORY = "WRONG_CATEGORY"
    PRICING_ISSUE = "PRICING_ISSUE"
    GEO_SCOPE_ISSUE = "GEO_SCOPE_ISSUE"
    ENTITLEMENTS_ISSUE = "ENTITLEMENTS_ISSUE"
    OTHER = "OTHER"


class ModerationQueueItem(BaseModel):
    type: ModerationEntityType
    id: str
    partner_id: str
    title: str
    status: ModerationStatus
    submitted_at: datetime | None = None
    updated_at: datetime | None = None


class ModerationQueueResponse(BaseModel):
    items: list[ModerationQueueItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class ModerationRejectRequest(BaseModel):
    reason_code: ModerationReasonCode
    comment: str = Field(min_length=10, max_length=2000)


class ModerationAuditItem(BaseModel):
    id: str
    actor_user_id: str | None = None
    actor_role: str | None = None
    action: ModerationAction
    reason_code: ModerationReasonCode | None = None
    comment: str | None = None
    before_status: ModerationStatus | None = None
    after_status: ModerationStatus | None = None
    created_at: datetime
    meta: dict | None = None


class ModerationAuditResponse(BaseModel):
    items: list[ModerationAuditItem] = Field(default_factory=list)


class ServiceModerationDetail(ServiceCardOut):
    locations: list[ServiceLocationOut] = Field(default_factory=list)
    schedule: ServiceScheduleOut | None = None
