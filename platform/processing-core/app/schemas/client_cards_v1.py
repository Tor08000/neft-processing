from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CardLimitOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit_type: str
    amount: float
    currency: str
    active: bool = True


class CardOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    pan_masked: str | None = None
    masked_pan: str | None = None
    issued_at: datetime | None = None
    limits: list[CardLimitOut] = Field(default_factory=list)


class CardListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CardOut]
    templates: list["CardTemplateSummary"] = Field(default_factory=list)


class CardTemplateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    is_default: bool = False


class CardCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pan_masked: str | None = None
    label: str | None = None
    template_id: str | None = None


class CardUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class CardLimitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit_type: str
    amount: float
    currency: str = "RUB"


class CardLimitsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limits: list[CardLimitRequest]


class CardAccessOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    scope: str
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class CardAccessListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CardAccessOut]


class CardAccessGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    scope: str


class CardTransactionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    card_id: str | None = None
    operation_type: str
    status: str
    amount: int
    currency: str
    performed_at: datetime


class UserRoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[str]


class BulkCardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_ids: list[str] = Field(min_length=1)


class BulkCardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: list[str]
    failed: dict[str, str]


class BulkCardAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_ids: list[str] = Field(min_length=1)
    user_id: str
    scope: str


class BulkApplyTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_ids: list[str] = Field(min_length=1)
    template_id: str


class LimitTemplateLimit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    value: float
    window: str


class LimitTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    limits: list[LimitTemplateLimit]


class LimitTemplateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    limits: list[LimitTemplateLimit] | None = None
    status: str | None = None


class LimitTemplateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    org_id: str
    name: str
    description: str | None = None
    limits: list[LimitTemplateLimit]
    status: str
    created_at: datetime


class LimitTemplateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LimitTemplateOut]
