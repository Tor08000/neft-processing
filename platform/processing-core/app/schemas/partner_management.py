from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PartnerOut(BaseModel):
    id: str
    code: str
    legal_name: str
    brand_name: str | None = None
    partner_type: str
    inn: str | None = None
    ogrn: str | None = None
    status: str
    contacts: dict[str, Any] = Field(default_factory=dict)


class PartnerMeOut(BaseModel):
    partner: PartnerOut
    my_roles: list[str] = Field(default_factory=list)


class PartnerCreate(BaseModel):
    code: str
    legal_name: str
    brand_name: str | None = None
    partner_type: str
    inn: str | None = None
    ogrn: str | None = None
    status: str = "PENDING"
    contacts: dict[str, Any] = Field(default_factory=dict)
    owner_user_email: str | None = None
    owner_user_id: str | None = None


class PartnerUpdate(BaseModel):
    status: str | None = None
    contacts: dict[str, Any] | None = None
    brand_name: str | None = None
    partner_type: str | None = None


class PartnerLocationCreate(BaseModel):
    external_id: str | None = None
    code: str | None = None
    title: str
    address: str
    city: str | None = None
    region: str | None = None
    lat: float | None = None
    lon: float | None = None
    status: str = "ACTIVE"


class PartnerLocationUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    lat: float | None = None
    lon: float | None = None
    status: str | None = None


class PartnerLocationOut(BaseModel):
    id: str
    partner_id: str
    external_id: str | None = None
    code: str | None = None
    title: str
    address: str
    city: str | None = None
    region: str | None = None
    lat: float | None = None
    lon: float | None = None
    status: str


class PartnerUserRoleCreate(BaseModel):
    user_id: str | None = None
    email: str | None = None
    roles: list[str] = Field(default_factory=list)


class PartnerUserRoleSelfCreate(BaseModel):
    user_id: str | None = None
    email: str | None = None
    roles: list[str] = Field(default_factory=list)


class PartnerUserRoleOut(BaseModel):
    user_id: str
    roles: list[str] = Field(default_factory=list)
    created_at: datetime


class PartnerMePatch(BaseModel):
    contacts: dict[str, Any] | None = None
    brand_name: str | None = None


class PartnerTermsOut(BaseModel):
    id: str
    partner_id: str
    version: int
    terms: dict[str, Any] = Field(default_factory=dict)
    status: str


class PartnerListOut(BaseModel):
    items: list[PartnerOut]
    page: int
    page_size: int
    total: int
