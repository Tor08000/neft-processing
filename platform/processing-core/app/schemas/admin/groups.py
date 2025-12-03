from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminFromAttributesModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClientGroupBase(AdminFromAttributesModel):
    group_id: str
    name: str
    description: str | None = None


class ClientGroupCreate(ClientGroupBase):
    pass


class ClientGroupUpdate(AdminFromAttributesModel):
    name: str | None = None
    description: str | None = None


class ClientGroupRead(ClientGroupBase):
    id: int
    created_at: datetime


class ClientGroupListResponse(AdminFromAttributesModel):
    items: list[ClientGroupRead]
    total: int
    limit: int
    offset: int


class ClientGroupMemberChange(BaseModel):
    client_id: str


class ClientGroupMemberRead(AdminFromAttributesModel):
    client_id: str
    created_at: datetime


class CardGroupBase(AdminFromAttributesModel):
    group_id: str
    name: str
    description: str | None = None


class CardGroupCreate(CardGroupBase):
    pass


class CardGroupUpdate(AdminFromAttributesModel):
    name: str | None = None
    description: str | None = None


class CardGroupRead(CardGroupBase):
    id: int
    created_at: datetime


class CardGroupListResponse(AdminFromAttributesModel):
    items: list[CardGroupRead]
    total: int
    limit: int
    offset: int


class CardGroupMemberChange(BaseModel):
    card_id: str


class CardGroupMemberRead(AdminFromAttributesModel):
    card_id: str
    created_at: datetime
