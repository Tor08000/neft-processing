from __future__ import annotations

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
