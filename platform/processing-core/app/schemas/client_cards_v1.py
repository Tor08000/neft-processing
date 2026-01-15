from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CardLimitOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit_type: str
    amount: float
    currency: str


class CardOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    pan_masked: str | None = None
    limits: list[CardLimitOut] = Field(default_factory=list)


class CardListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CardOut]


class CardCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pan_masked: str | None = None


class CardUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class CardLimitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit_type: str
    amount: float
    currency: str = "RUB"


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
