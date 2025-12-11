from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PartnerBase(BaseModel):
    id: str
    name: str
    type: Literal["AZS", "aggregator"]
    status: Literal["active", "disabled"] = "active"
    allowed_ips: list[str] = Field(default_factory=list)


class PartnerCreate(PartnerBase):
    token: str


class PartnerUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[Literal["AZS", "aggregator"]] = None
    status: Optional[Literal["active", "disabled"]] = None
    allowed_ips: Optional[list[str]] = None
    token: Optional[str] = None


class PartnerSchema(PartnerBase):
    model_config = ConfigDict(from_attributes=True)

    token: str
    created_at: Optional[str] = None
