from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, constr


MerchantId = constr(strip_whitespace=True, min_length=1, max_length=64)
TerminalId = constr(strip_whitespace=True, min_length=1, max_length=64)
MerchantName = constr(strip_whitespace=True, min_length=1, max_length=255)
StatusValue = constr(strip_whitespace=True, min_length=1, max_length=32)
LocationValue = constr(strip_whitespace=True, min_length=0, max_length=255)


class MerchantBase(BaseModel):
    name: MerchantName
    status: StatusValue


class MerchantCreate(MerchantBase):
    id: MerchantId


class MerchantUpdate(BaseModel):
    name: Optional[MerchantName] = None
    status: Optional[StatusValue] = None


class MerchantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str


class MerchantListResponse(BaseModel):
    items: List[MerchantRead]
    total: int
    limit: int
    offset: int


class TerminalBase(BaseModel):
    merchant_id: MerchantId
    status: StatusValue
    location: Optional[LocationValue] = Field(default=None)


class TerminalCreate(TerminalBase):
    id: TerminalId


class TerminalUpdate(BaseModel):
    merchant_id: Optional[MerchantId] = None
    status: Optional[StatusValue] = None
    location: Optional[LocationValue] = Field(default=None)


class TerminalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_id: str
    status: str
    location: Optional[str] = None


class TerminalListResponse(BaseModel):
    items: List[TerminalRead]
    total: int
    limit: int
    offset: int
