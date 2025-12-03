from datetime import datetime

from pydantic import BaseModel


class ClientGroupBase(BaseModel):
    group_id: str
    name: str
    description: str | None = None

    class Config:
        orm_mode = True
        from_attributes = True


class ClientGroupCreate(ClientGroupBase):
    pass


class ClientGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

    class Config:
        orm_mode = True
        from_attributes = True


class ClientGroupRead(ClientGroupBase):
    id: int
    created_at: datetime


class ClientGroupListResponse(BaseModel):
    items: list[ClientGroupRead]
    total: int
    limit: int
    offset: int

    class Config:
        orm_mode = True
        from_attributes = True


class ClientGroupMemberChange(BaseModel):
    client_id: str


class ClientGroupMemberRead(BaseModel):
    client_id: str
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class CardGroupBase(BaseModel):
    group_id: str
    name: str
    description: str | None = None

    class Config:
        orm_mode = True
        from_attributes = True


class CardGroupCreate(CardGroupBase):
    pass


class CardGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

    class Config:
        orm_mode = True
        from_attributes = True


class CardGroupRead(CardGroupBase):
    id: int
    created_at: datetime


class CardGroupListResponse(BaseModel):
    items: list[CardGroupRead]
    total: int
    limit: int
    offset: int

    class Config:
        orm_mode = True
        from_attributes = True


class CardGroupMemberChange(BaseModel):
    card_id: str


class CardGroupMemberRead(BaseModel):
    card_id: str
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True
