from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ClientGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ClientGroupCreate(ClientGroupBase):
    pass


class ClientGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class ClientGroupResponse(ClientGroupBase):
    id: int
    members: List[str] = []

    class Config:
        orm_mode = True


class CardGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class CardGroupCreate(CardGroupBase):
    pass


class CardGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class CardGroupResponse(CardGroupBase):
    id: int
    members: List[str] = []

    class Config:
        orm_mode = True


class MembershipRequest(BaseModel):
    member_id: str = Field(..., min_length=1, max_length=64)


class LimitRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    daily_limit: int = Field(..., ge=0)
    limit_per_tx: int = Field(..., ge=0)
    priority: int = 0
    currency: str = Field("RUB", min_length=1, max_length=8)
    client_group_id: Optional[int] = None
    card_group_id: Optional[int] = None


class LimitRuleCreate(LimitRuleBase):
    pass


class LimitRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    daily_limit: Optional[int] = Field(None, ge=0)
    limit_per_tx: Optional[int] = Field(None, ge=0)
    priority: Optional[int] = None
    currency: Optional[str] = Field(None, min_length=1, max_length=8)
    client_group_id: Optional[int] = None
    card_group_id: Optional[int] = None


class LimitRuleResponse(LimitRuleBase):
    id: int

    class Config:
        orm_mode = True
