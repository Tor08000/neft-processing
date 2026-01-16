from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClientOrgIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_type: str = Field(..., description="LEGAL/IP/INDIVIDUAL")
    name: str = Field(..., min_length=1)
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    address: str | None = None


class ClientOrgOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    org_type: str | None = None
    name: str
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    address: str | None = None
    status: str


class ContractInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: str
    status: str
    pdf_url: str | None = None
    version: int | None = None


class ContractSignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    otp: str


class ClientSubscriptionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str
    status: str | None = None
    modules: dict[str, dict[str, Any]]
    limits: dict[str, dict[str, Any]]


class ClientSubscriptionSelectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str
    auto_renew: bool = False
    duration_months: int | None = None


class ClientUserInviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    role: str


class ClientUserSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    role: str
    status: str | None = None
    last_login: str | None = None


class ClientUsersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClientUserSummary]


class ClientDocSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    status: str
    date: date
    download_url: str


class ClientDocsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClientDocSummary]


class ClientAuditEventSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    created_at: datetime
    org_id: str | None = None
    actor_user_id: str | None = None
    actor_label: str | None = None
    action: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    entity_label: str | None = None
    request_id: str | None = None
    ip: str | None = None
    ua: str | None = None
    result: str | None = None
    summary: str | None = None


class ClientAuditEventsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClientAuditEventSummary]
    next_cursor: str | None = None
